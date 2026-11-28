#include <QApplication>
#include <QCheckBox>
#include <QClipboard>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSplitter>
#include <QTabWidget>
#include <QTreeWidget>
#include <QVBoxLayout>

#include "pages.h"
#include "theme.h"
#include "widgets.h"

InspectorPage::InspectorPage(QWidget* parent) : QWidget(parent) {
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(28, 24, 28, 24);
  root->setSpacing(16);

  auto* tools = new QWidget;
  auto* th = new QHBoxLayout(tools);
  th->setContentsMargins(0, 0, 0, 0);
  filter_ = new QLineEdit;
  filter_->setPlaceholderText(tr("Filter by path or status…"));
  filter_->setClearButtonEnabled(true);
  filter_->setMinimumWidth(220);
  showPolls_ = new QCheckBox(tr("Show polls"));
  showPolls_->setChecked(true);
  showPolls_->setToolTip(tr("Background polls (/health, /state) are kept as the latest one per endpoint"));
  auto* clear = new QPushButton(tr("Clear"));
  clear->setProperty("kind", "ghost");
  th->addWidget(filter_);
  th->addWidget(showPolls_);
  th->addWidget(clear);
  root->addWidget(makePageHeader(tr("Inspector"), tr("Every response the app received, as a tree or raw JSON."), tools));

  auto* split = new QSplitter(Qt::Horizontal);
  split->setHandleWidth(16);
  split->setChildrenCollapsible(false);

  QVBoxLayout* lv = nullptr;
  QFrame* left = makePanel(tr("Exchanges"), &lv);
  list_ = new QTreeWidget;
  list_->setHeaderLabels({tr("Time"), tr("Request"), tr("Status"), tr("ms")});
  list_->setRootIsDecorated(false);
  list_->setProperty("mono", true);
  list_->header()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
  list_->header()->setSectionResizeMode(1, QHeaderView::Stretch);
  list_->header()->setSectionResizeMode(2, QHeaderView::ResizeToContents);
  list_->header()->setSectionResizeMode(3, QHeaderView::ResizeToContents);
  list_->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
  list_->setFrameShape(QFrame::NoFrame);
  lv->addWidget(list_);
  left->setMinimumWidth(420);
  split->addWidget(left);

  QVBoxLayout* rv = nullptr;
  QFrame* right = makePanel(QString(), &rv);
  auto* hh = new QHBoxLayout;
  head_ = makeLabel(tr("Select an exchange"), "metricSmall");
  head_->setTextInteractionFlags(Qt::TextSelectableByMouse);
  status_ = new Pill(tr("—"), Tone::Neutral);
  auto* copy = new QPushButton(tr("Copy body"));
  copy->setProperty("kind", "ghost");
  hh->addWidget(head_, 1);
  hh->addWidget(status_);
  hh->addWidget(copy);
  rv->addLayout(hh);
  tabs_ = new QTabWidget;
  tree_ = new QTreeWidget;
  tree_->setHeaderLabels({tr("Key"), tr("Value")});
  tree_->setProperty("mono", true);
  tree_->header()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
  tree_->setFrameShape(QFrame::NoFrame);
  raw_ = new QPlainTextEdit;
  raw_->setReadOnly(true);
  request_ = new QPlainTextEdit;
  request_->setReadOnly(true);
  image_ = new ImageView(tr("Not an image response"));
  tabs_->addTab(tree_, tr("Tree"));
  tabs_->addTab(raw_, tr("Raw"));
  tabs_->addTab(request_, tr("Request"));
  tabs_->addTab(image_, tr("Image"));
  rv->addWidget(tabs_, 1);
  split->addWidget(right);
  split->setStretchFactor(0, 2);
  split->setStretchFactor(1, 3);
  root->addWidget(split, 1);

  connect(list_, &QTreeWidget::currentItemChanged, this, [this](QTreeWidgetItem* it) {
    if (it) show(it->data(0, Qt::UserRole).toInt());
  });
  connect(filter_, &QLineEdit::textChanged, this, &InspectorPage::rebuildList);
  connect(showPolls_, &QCheckBox::toggled, this, &InspectorPage::rebuildList);
  connect(clear, &QPushButton::clicked, this, [this] {
    items_.clear();
    current_ = -1;
    rebuildList();
  });
  connect(copy, &QPushButton::clicked, this, [this] {
    if (current_ >= 0 && current_ < items_.size())
      QApplication::clipboard()->setText(prettyJson(items_[current_].body));
  });
}

void InspectorPage::record(const ApiResult& r) {
  // Polls replace their previous sample so they never flood the history.
  if (r.quiet) {
    for (int i = 0; i < items_.size(); ++i) {
      if (items_[i].quiet && items_[i].method == r.method && items_[i].path == r.path) {
        items_.remove(i);
        if (current_ == i) current_ = -2;  // re-select the replacement below
        else if (current_ > i) --current_;
        break;
      }
    }
  }
  items_.push_back(r);
  const int cap = cfg::get(cfg::kHistory).toInt();
  while (items_.size() > std::max(20, cap)) {
    items_.pop_front();
    if (current_ >= 0) --current_;
  }
  if (current_ == -2) current_ = items_.size() - 1;
  if (isVisible()) rebuildList();
}

void InspectorPage::rebuildList() {
  const QString f = filter_->text().trimmed();
  const ThemeColors& c = Theme::colors();
  const int keep = current_;
  list_->blockSignals(true);
  list_->clear();
  QTreeWidgetItem* sel = nullptr;
  for (int i = items_.size() - 1; i >= 0; --i) {
    const ApiResult& r = items_[i];
    if (r.quiet && !showPolls_->isChecked()) continue;
    const QString req = QStringLiteral("%1 %2").arg(r.method, r.path);
    if (!f.isEmpty() && !req.contains(f, Qt::CaseInsensitive) && !QString::number(r.status).contains(f)) continue;
    auto* it = new QTreeWidgetItem(list_);
    it->setText(0, r.when.toString(QStringLiteral("HH:mm:ss")));
    it->setText(1, r.quiet ? req + QStringLiteral("  ⟳") : req);
    it->setText(2, r.reachable() ? QString::number(r.status) : QStringLiteral("—"));
    it->setText(3, QString::number(r.elapsedMs));
    it->setData(0, Qt::UserRole, i);
    it->setForeground(0, c.faint);
    it->setForeground(2, r.ok() ? c.success : r.reachable() ? c.warning : c.danger);
    it->setForeground(3, c.faint);
    if (i == keep) sel = it;
  }
  list_->blockSignals(false);
  if (!sel && keep == -1 && list_->topLevelItemCount() > 0) {
    sel = list_->topLevelItem(0);
    current_ = sel->data(0, Qt::UserRole).toInt();
  }
  if (sel) {
    list_->setCurrentItem(sel);
    show(current_);
  }
}

void InspectorPage::show(int row) {
  if (row < 0 || row >= items_.size()) return;
  current_ = row;
  const ApiResult& r = items_[row];
  head_->setText(QStringLiteral("%1 %2").arg(r.method, r.path));
  status_->set(r.reachable() ? QStringLiteral("%1 · %2 ms").arg(r.statusText()).arg(r.elapsedMs) : r.error,
               r.ok() ? Tone::Success : r.reachable() ? Tone::Warning : Tone::Danger);
  if (r.isJson()) {
    fillJsonTree(tree_, r.json.isObject() ? QJsonValue(r.json.object()) : QJsonValue(r.json.array()));
    raw_->setPlainText(prettyJson(r.body));
  } else {
    fillJsonTree(tree_, QJsonValue(QJsonValue::Undefined));
    const QImage img = QImage::fromData(r.body);
    raw_->setPlainText(img.isNull() ? QString::fromUtf8(r.body.left(64 * 1024))
                                    : tr("<%1 image, %2 × %3, %4>")
                                          .arg(r.contentType)
                                          .arg(img.width())
                                          .arg(img.height())
                                          .arg(fmtBytes(r.body.size())));
  }
  const QImage img = r.isJson() ? QImage() : QImage::fromData(r.body);
  image_->setImage(img);
  QString req = QStringLiteral("%1 %2\n\n").arg(r.method, r.url.toString());
  if (!r.requestBody.isEmpty()) req += prettyJson(r.requestBody);
  else if (!r.requestSummary.isEmpty()) req += r.requestSummary;
  else req += tr("(no body)");
  if (!r.contentType.isEmpty()) req += tr("\n\nResponse Content-Type: %1").arg(r.contentType);
  request_->setPlainText(req);
  if (!img.isNull() && tabs_->currentWidget() != image_) tabs_->setCurrentWidget(image_);
  else if (img.isNull() && tabs_->currentWidget() == image_) tabs_->setCurrentWidget(tree_);
}

void InspectorPage::showEvent(QShowEvent* e) {
  rebuildList();
  QWidget::showEvent(e);
}
