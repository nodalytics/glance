#include <QCheckBox>
#include <QComboBox>
#include <QFormLayout>
#include <QLabel>
#include <QSpinBox>
#include <QVBoxLayout>

#include "pages.h"
#include "widgets.h"

namespace {

QSpinBox* msSpin(int min, int max, int step) {
  auto* s = new QSpinBox;
  s->setRange(min, max);
  s->setSingleStep(step);
  s->setSuffix(QStringLiteral(" ms"));
  s->setMinimumWidth(140);
  return s;
}

}  // namespace

SettingsPage::SettingsPage(QWidget* parent) : QWidget(parent) {
  auto* body = new QWidget;
  auto* root = new QVBoxLayout(body);
  root->setContentsMargins(28, 24, 28, 28);
  root->setSpacing(16);
  root->addWidget(makePageHeader(tr("Settings"), tr("Saved automatically with QSettings.")));

  auto makeForm = [](QVBoxLayout* v) {
    auto* f = new QFormLayout;
    f->setLabelAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    f->setFormAlignment(Qt::AlignLeft | Qt::AlignTop);
    f->setHorizontalSpacing(28);
    f->setVerticalSpacing(14);
    f->setFieldGrowthPolicy(QFormLayout::FieldsStayAtSizeHint);
    v->addLayout(f);
    return f;
  };

  QVBoxLayout* av = nullptr;
  QFrame* appearance = makePanel(tr("Appearance"), &av);
  QFormLayout* af = makeForm(av);
  theme_ = new QComboBox;
  theme_->addItem(tr("Dark"), QStringLiteral("dark"));
  theme_->addItem(tr("Light"), QStringLiteral("light"));
  theme_->addItem(tr("Follow system"), QStringLiteral("system"));
  theme_->setCurrentIndex(std::max(0, theme_->findData(cfg::get(cfg::kTheme))));
  theme_->setMinimumWidth(180);
  af->addRow(makeLabel(tr("Theme"), "muted"), theme_);
  root->addWidget(appearance);

  QVBoxLayout* cv = nullptr;
  QFrame* conn = makePanel(tr("Connection & polling"), &cv);
  QFormLayout* cf = makeForm(cv);
  health_ = msSpin(250, 60000, 250);
  health_->setValue(cfg::get(cfg::kHealthMs).toInt());
  state_ = msSpin(100, 60000, 100);
  state_->setValue(cfg::get(cfg::kStateMs).toInt());
  timeout_ = msSpin(250, 120000, 250);
  timeout_->setValue(cfg::get(cfg::kTimeoutMs).toInt());
  autoConnect_ = new QCheckBox(tr("Connect on start-up"));
  autoConnect_->setChecked(cfg::get(cfg::kAutoConnect).toBool());
  cf->addRow(makeLabel(tr("Health poll"), "muted"), health_);
  cf->addRow(makeLabel(tr("State poll"), "muted"), state_);
  cf->addRow(makeLabel(tr("Request timeout"), "muted"), timeout_);
  cf->addRow(makeLabel(tr("Start-up"), "muted"), autoConnect_);
  root->addWidget(conn);

  QVBoxLayout* bv = nullptr;
  QFrame* beh = makePanel(tr("Behaviour"), &bv);
  QFormLayout* bf = makeForm(bv);
  confirm_ = new QCheckBox(tr("Ask before /click, /key and /sequence"));
  confirm_->setChecked(cfg::get(cfg::kConfirm).toBool());
  autoFrame_ = new QCheckBox(tr("Fetch /frame.png after every capture"));
  autoFrame_->setChecked(cfg::get(cfg::kAutoFrame).toBool());
  bf->addRow(makeLabel(tr("Input safety"), "muted"), confirm_);
  bf->addRow(makeLabel(tr("Capture"), "muted"), autoFrame_);
  root->addWidget(beh);

  QVBoxLayout* iv = nullptr;
  QFrame* about = makePanel(tr("About"), &iv);
  auto* a = makeLabel(tr("glance-admin %1 — a Qt %2 client of the glance HTTP API. It links only QtWidgets and "
                         "QtNetwork, so it runs on machines without OpenCV.")
                          .arg(QStringLiteral(GLANCE_ADMIN_VERSION), QString::fromLatin1(qVersion())),
                      "muted");
  a->setWordWrap(true);
  iv->addWidget(a);
  QSettings s;
  iv->addWidget(makeLabel(tr("Settings file: %1").arg(s.fileName()), "mono"));
  root->addWidget(about);
  root->addStretch();

  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  lay->addWidget(scrollPage(body));

  connect(theme_, &QComboBox::currentIndexChanged, this, [this] {
    const QString t = theme_->currentData().toString();
    cfg::set(cfg::kTheme, t);
    Q_EMIT themeChanged(t);
  });
  connect(health_, &QSpinBox::valueChanged, this, [this](int v) {
    cfg::set(cfg::kHealthMs, v);
    Q_EMIT pollingChanged();
  });
  connect(state_, &QSpinBox::valueChanged, this, [this](int v) {
    cfg::set(cfg::kStateMs, v);
    Q_EMIT pollingChanged();
  });
  connect(timeout_, &QSpinBox::valueChanged, this, [this](int v) {
    cfg::set(cfg::kTimeoutMs, v);
    Q_EMIT pollingChanged();
  });
  connect(autoConnect_, &QCheckBox::toggled, this, [](bool on) { cfg::set(cfg::kAutoConnect, on); });
  connect(confirm_, &QCheckBox::toggled, this, [](bool on) { cfg::set(cfg::kConfirm, on); });
  connect(autoFrame_, &QCheckBox::toggled, this, [](bool on) { cfg::set(cfg::kAutoFrame, on); });
}

void SettingsPage::showEvent(QShowEvent* e) {
  // Other pages edit some of the same keys (theme toggle, confirm box, poll
  // interval); re-read them so this page never shows stale values.
  const QSignalBlocker b1(theme_), b2(health_), b3(state_), b4(timeout_), b5(confirm_), b6(autoFrame_),
      b7(autoConnect_);
  theme_->setCurrentIndex(std::max(0, theme_->findData(cfg::get(cfg::kTheme))));
  health_->setValue(cfg::get(cfg::kHealthMs).toInt());
  state_->setValue(cfg::get(cfg::kStateMs).toInt());
  timeout_->setValue(cfg::get(cfg::kTimeoutMs).toInt());
  confirm_->setChecked(cfg::get(cfg::kConfirm).toBool());
  autoFrame_->setChecked(cfg::get(cfg::kAutoFrame).toBool());
  autoConnect_->setChecked(cfg::get(cfg::kAutoConnect).toBool());
  QWidget::showEvent(e);
}
