#include <QCheckBox>
#include <QComboBox>
#include <QDateTime>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSpinBox>
#include <QStackedWidget>
#include <QTreeWidget>
#include <QVBoxLayout>

#include "pages.h"
#include "theme.h"
#include "widgets.h"

namespace {

QSpinBox* coordSpin(int max = 16384) {
  auto* s = new QSpinBox;
  s->setRange(0, max);
  s->setMinimumWidth(72);
  return s;
}

QWidget* labeled(const QString& label, QWidget* w) {
  auto* box = new QWidget;
  auto* v = new QVBoxLayout(box);
  v->setContentsMargins(0, 0, 0, 0);
  v->setSpacing(4);
  v->addWidget(makeLabel(label, "faint"));
  v->addWidget(w);
  return box;
}

const char* kDefaultSequence = R"([
  {"action": "call"},
  {"click": {"x": 820, "y": 600}},
  {"type": "200"},
  {"key": "Return"}
])";

}  // namespace

ControlPage::ControlPage(ApiClient* api, QWidget* parent) : QWidget(parent), api_(api) {
  auto* body = new QWidget;
  auto* root = new QVBoxLayout(body);
  root->setContentsMargins(28, 24, 28, 28);
  root->setSpacing(16);
  backend_ = new Pill(tr("backend unknown"), Tone::Neutral);
  root->addWidget(makePageHeader(tr("Control"),
                                 tr("Drive the platform back: grabs, clicks, keys and scripted sequences."),
                                 backend_));

  // ---- safety
  {
    QVBoxLayout* v = nullptr;
    QFrame* p = makePanel(QString(), &v);
    auto* h = new QHBoxLayout;
    confirm_ = new QCheckBox(tr("Confirm before injecting input"));
    confirm_->setChecked(cfg::get(cfg::kConfirm).toBool());
    connect(confirm_, &QCheckBox::toggled, this, [](bool on) { cfg::set(cfg::kConfirm, on); });
    h->addWidget(confirm_);
    h->addStretch();
    backendNote_ = makeLabel(tr("Clicks and keys go to the real desktop of the machine running glance-server."),
                             "muted");
    h->addWidget(backendNote_);
    v->addLayout(h);
    root->addWidget(p);
  }

  auto* grid = new QGridLayout;
  grid->setSpacing(16);

  // ---- grab
  {
    QVBoxLayout* v = nullptr;
    QFrame* p = makePanel(tr("Grab  ·  POST /grab"), &v);
    grabMode_ = new QComboBox;
    grabMode_->addItems({tr("Mapping window"), tr("Window by title"), tr("Screen region")});
    v->addWidget(grabMode_);
    grabStack_ = new QStackedWidget;
    grabStack_->addWidget(makeLabel(tr("Grabs the window named by the mapping's window_title."), "faint"));
    grabTitle_ = new QLineEdit;
    grabTitle_->setPlaceholderText(tr("Window title, e.g. ACR Poker"));
    grabStack_->addWidget(grabTitle_);
    auto* region = new QWidget;
    auto* rh = new QHBoxLayout(region);
    rh->setContentsMargins(0, 0, 0, 0);
    gx_ = coordSpin();
    gy_ = coordSpin();
    gw_ = coordSpin();
    gh_ = coordSpin();
    gw_->setValue(1280);
    gh_->setValue(720);
    rh->addWidget(labeled(QStringLiteral("x"), gx_));
    rh->addWidget(labeled(QStringLiteral("y"), gy_));
    rh->addWidget(labeled(QStringLiteral("w"), gw_));
    rh->addWidget(labeled(QStringLiteral("h"), gh_));
    grabStack_->addWidget(region);
    v->addWidget(grabStack_);
    connect(grabMode_, &QComboBox::currentIndexChanged, grabStack_, &QStackedWidget::setCurrentIndex);
    v->addStretch();
    auto* go = new QPushButton(tr("Grab"));
    go->setProperty("kind", "primary");
    auto* bh = new QHBoxLayout;
    bh->addStretch();
    bh->addWidget(go);
    v->addLayout(bh);
    connect(go, &QPushButton::clicked, this, [this] {
      QJsonObject b;
      if (grabMode_->currentIndex() == 1) {
        if (grabTitle_->text().trimmed().isEmpty()) {
          grabTitle_->setFocus();
          return;
        }
        b[QStringLiteral("title")] = grabTitle_->text().trimmed();
      } else if (grabMode_->currentIndex() == 2) {
        b[QStringLiteral("region")] = QJsonObject{{QStringLiteral("x"), gx_->value()},
                                                  {QStringLiteral("y"), gy_->value()},
                                                  {QStringLiteral("w"), gw_->value()},
                                                  {QStringLiteral("h"), gh_->value()}};
      }
      post(QStringLiteral("/grab"), QJsonDocument(b), false, tr("grab"));
    });
    grid->addWidget(p, 0, 0);
  }

  // ---- keyboard
  {
    QVBoxLayout* v = nullptr;
    QFrame* p = makePanel(tr("Keyboard  ·  POST /key"), &v);
    auto* kh = new QHBoxLayout;
    keysym_ = new QLineEdit;
    keysym_->setPlaceholderText(tr("X keysym: Return, Tab, F5, a…"));
    auto* press = new QPushButton(tr("Press"));
    kh->addWidget(keysym_, 1);
    kh->addWidget(press);
    v->addLayout(kh);
    auto* quick = new QHBoxLayout;
    quick->setSpacing(6);
    for (const char* k : {"Return", "Tab", "Escape", "BackSpace", "space"}) {
      auto* b = new QPushButton(QString::fromLatin1(k));
      b->setProperty("kind", "chip");
      connect(b, &QPushButton::clicked, this, [this, k] {
        post(QStringLiteral("/key"), QJsonDocument(QJsonObject{{QStringLiteral("key"), QString::fromLatin1(k)}}),
             true, tr("press %1").arg(QString::fromLatin1(k)));
      });
      quick->addWidget(b);
    }
    quick->addStretch();
    v->addLayout(quick);
    v->addWidget(makeDivider());
    auto* th = new QHBoxLayout;
    text_ = new QLineEdit;
    text_->setPlaceholderText(tr("Text to type, e.g. a bet size"));
    auto* type = new QPushButton(tr("Type"));
    th->addWidget(text_, 1);
    th->addWidget(type);
    v->addLayout(th);
    v->addStretch();
    auto pressKey = [this] {
      const QString k = keysym_->text().trimmed();
      if (k.isEmpty()) return keysym_->setFocus();
      post(QStringLiteral("/key"), QJsonDocument(QJsonObject{{QStringLiteral("key"), k}}), true,
           tr("press %1").arg(k));
    };
    auto typeText = [this] {
      const QString t = text_->text();
      if (t.isEmpty()) return text_->setFocus();
      post(QStringLiteral("/key"), QJsonDocument(QJsonObject{{QStringLiteral("type"), t}}), true,
           tr("type \"%1\"").arg(t));
    };
    connect(press, &QPushButton::clicked, this, pressKey);
    connect(keysym_, &QLineEdit::returnPressed, this, pressKey);
    connect(type, &QPushButton::clicked, this, typeText);
    connect(text_, &QLineEdit::returnPressed, this, typeText);
    grid->addWidget(p, 0, 1);
  }

  // ---- click
  {
    QVBoxLayout* v = nullptr;
    QFrame* p = makePanel(tr("Click  ·  POST /click"), &v);
    v->addWidget(makeLabel(tr("Named actions"), "faint"));
    actionsBox_ = new QWidget;
    actionsGrid_ = new QGridLayout(actionsBox_);
    actionsGrid_->setContentsMargins(0, 0, 0, 0);
    actionsGrid_->setSpacing(6);
    v->addWidget(actionsBox_);
    auto* th = new QHBoxLayout;
    target_ = new QComboBox;
    target_->setEditable(true);
    target_->lineEdit()->setPlaceholderText(tr("action name or button:/stack: target"));
    auto* go = new QPushButton(tr("Click target"));
    th->addWidget(target_, 1);
    th->addWidget(go);
    v->addLayout(th);
    v->addWidget(makeDivider());
    v->addWidget(makeLabel(tr("Raw point in the last captured frame's space (pick one on the Capture page)"), "faint"));
    auto* ch = new QHBoxLayout;
    cx_ = coordSpin();
    cy_ = coordSpin();
    button_ = new QComboBox;
    button_->addItems({tr("Left"), tr("Middle"), tr("Right")});
    ch->addWidget(labeled(QStringLiteral("x"), cx_));
    ch->addWidget(labeled(QStringLiteral("y"), cy_));
    ch->addWidget(labeled(tr("button"), button_));
    ch->addStretch();
    auto* clickPt = new QPushButton(tr("Click point"));
    ch->addWidget(clickPt, 0, Qt::AlignBottom);
    v->addLayout(ch);
    connect(go, &QPushButton::clicked, this, [this] {
      const QString t = target_->currentText().trimmed();
      if (t.isEmpty()) return target_->setFocus();
      post(QStringLiteral("/click"), QJsonDocument(QJsonObject{{QStringLiteral("action"), t}}), true,
           tr("click \"%1\"").arg(t));
    });
    connect(clickPt, &QPushButton::clicked, this, [this] {
      QJsonObject c{{QStringLiteral("x"), cx_->value()},
                    {QStringLiteral("y"), cy_->value()},
                    {QStringLiteral("button"), button_->currentIndex() + 1}};
      post(QStringLiteral("/click"), QJsonDocument(QJsonObject{{QStringLiteral("click"), c}}), true,
           tr("%1-click at %2, %3").arg(button_->currentText().toLower()).arg(cx_->value()).arg(cy_->value()));
    });
    grid->addWidget(p, 1, 0);
  }

  // ---- sequence
  {
    QVBoxLayout* v = nullptr;
    QFrame* p = makePanel(tr("Sequence  ·  POST /sequence"), &v);
    sequence_ = new QPlainTextEdit;
    sequence_->setPlainText(QString::fromLatin1(kDefaultSequence));
    sequence_->setMinimumHeight(150);
    v->addWidget(sequence_, 1);
    auto* bh = new QHBoxLayout;
    seqStatus_ = makeLabel(tr("A JSON array of action / click / key / type steps."), "faint");
    bh->addWidget(seqStatus_, 1);
    auto* fmt = new QPushButton(tr("Format"));
    fmt->setProperty("kind", "ghost");
    auto* run = new QPushButton(tr("Run sequence"));
    run->setProperty("kind", "primary");
    bh->addWidget(fmt);
    bh->addWidget(run);
    v->addLayout(bh);
    auto parse = [this](QJsonDocument* out) {
      QJsonParseError pe;
      const QJsonDocument d = QJsonDocument::fromJson(sequence_->toPlainText().toUtf8(), &pe);
      if (pe.error != QJsonParseError::NoError) {
        seqStatus_->setText(tr("JSON error at %1: %2").arg(pe.offset).arg(pe.errorString()));
        return false;
      }
      if (!d.isArray()) {
        seqStatus_->setText(tr("The body must be a JSON array of steps."));
        return false;
      }
      *out = d;
      seqStatus_->setText(tr("%1 step(s), valid JSON.").arg(d.array().size()));
      return true;
    };
    connect(fmt, &QPushButton::clicked, this, [this, parse] {
      QJsonDocument d;
      if (parse(&d)) sequence_->setPlainText(QString::fromUtf8(d.toJson(QJsonDocument::Indented)));
    });
    connect(run, &QPushButton::clicked, this, [this, parse] {
      QJsonDocument d;
      if (parse(&d)) post(QStringLiteral("/sequence"), d, true, tr("run a %1-step sequence").arg(d.array().size()));
    });
    grid->addWidget(p, 1, 1);
  }
  grid->setColumnStretch(0, 1);
  grid->setColumnStretch(1, 1);
  root->addLayout(grid);

  // ---- log
  {
    QVBoxLayout* v = nullptr;
    QFrame* p = makePanel(tr("Activity"), &v);
    auto* hh = new QHBoxLayout;
    hh->addWidget(makeLabel(tr("Every control request and its response, newest first."), "faint"), 1);
    auto* clear = new QPushButton(tr("Clear"));
    clear->setProperty("kind", "ghost");
    hh->addWidget(clear);
    v->addLayout(hh);
    log_ = new QTreeWidget;
    log_->setHeaderLabels({tr("Time"), tr("Request"), tr("Status"), tr("ms"), tr("Response")});
    log_->setRootIsDecorated(false);
    log_->setProperty("mono", true);
    log_->setMinimumHeight(200);
    log_->header()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
    log_->header()->setSectionResizeMode(1, QHeaderView::Interactive);
    log_->header()->setSectionResizeMode(2, QHeaderView::ResizeToContents);
    log_->header()->setSectionResizeMode(3, QHeaderView::ResizeToContents);
    log_->header()->setStretchLastSection(true);
    log_->setColumnWidth(1, 300);
    v->addWidget(log_);
    connect(clear, &QPushButton::clicked, log_, &QTreeWidget::clear);
    root->addWidget(p);
  }

  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  lay->addWidget(scrollPage(body));
  rebuildActions();
}

void ControlPage::setBackend(const QString& backend) {
  if (backend.isEmpty()) {
    backend_->set(tr("backend unknown"), Tone::Neutral);
    return;
  }
  const bool null = backend == QLatin1String("null");
  backend_->set(tr("backend: %1").arg(backend), null ? Tone::Warning : Tone::Success);
  backendNote_->setText(null ? tr("Null backend: the server accepts requests but injects nothing and cannot grab.")
                             : tr("Clicks and keys go to the real desktop of the machine running glance-server."));
}

void ControlPage::setActions(const QStringList& names) {
  if (names == actions_) return;
  actions_ = names;
  rebuildActions();
}

void ControlPage::rebuildActions() {
  while (QLayoutItem* it = actionsGrid_->takeAt(0)) {
    delete it->widget();
    delete it;
  }
  QStringList names = actions_;
  const bool fromServer = !names.isEmpty();
  if (!fromServer)
    names = {QStringLiteral("fold"), QStringLiteral("check"), QStringLiteral("call"), QStringLiteral("raise")};
  const QString current = target_->currentText();
  target_->clear();
  target_->addItems(names);
  target_->setEditText(current);
  int i = 0;
  for (const QString& n : names) {
    auto* b = new QPushButton(n);
    b->setProperty("kind", "chip");
    b->setToolTip(fromServer ? tr("Mapping action \"%1\"").arg(n)
                             : tr("Common action name; the mapping may not define it"));
    connect(b, &QPushButton::clicked, this, [this, n] {
      post(QStringLiteral("/click"), QJsonDocument(QJsonObject{{QStringLiteral("action"), n}}), true,
           tr("click \"%1\"").arg(n));
    });
    actionsGrid_->addWidget(b, i / 4, i % 4);
    ++i;
  }
}

void ControlPage::setClickPoint(QPoint p) {
  cx_->setValue(p.x());
  cy_->setValue(p.y());
}

bool ControlPage::confirm(const QString& what) {
  if (!confirm_->isChecked()) return true;
  QMessageBox box(this);
  box.setWindowTitle(tr("Inject input?"));
  box.setIcon(QMessageBox::Warning);
  box.setText(tr("Send <b>%1</b> to %2?").arg(what.toHtmlEscaped(), api_->baseUrl().toString().toHtmlEscaped()));
  box.setInformativeText(tr("The server will inject real mouse/keyboard input on its desktop."));
  box.setStandardButtons(QMessageBox::Yes | QMessageBox::Cancel);
  box.setDefaultButton(QMessageBox::Cancel);
  box.button(QMessageBox::Yes)->setText(tr("Send input"));
  return box.exec() == QMessageBox::Yes;
}

void ControlPage::post(const QString& path, const QJsonDocument& body, bool input, const QString& what) {
  if (input && !confirm(what)) return;
  api_->postJson(path, body, [this, path](const ApiResult& r) {
    logResult(r);
    if (path == QLatin1String("/grab") && r.ok()) {
      const QJsonObject o = r.object();
      if (o.value(QStringLiteral("state")).isObject()) Q_EMIT stateReceived(o.value(QStringLiteral("state")).toObject());
      Q_EMIT grabbed();
    }
  });
}

void ControlPage::logResult(const ApiResult& r) {
  auto* it = new QTreeWidgetItem;
  it->setText(0, r.when.toString(QStringLiteral("HH:mm:ss")));
  QString req = QStringLiteral("%1 %2").arg(r.method, r.path);
  if (!r.requestBody.isEmpty() && r.requestBody != "{}") req += QLatin1Char(' ') + QString::fromUtf8(r.requestBody);
  it->setText(1, req);
  it->setToolTip(1, req);
  it->setText(2, r.reachable() ? QString::number(r.status) : tr("offline"));
  it->setText(3, QString::number(r.elapsedMs));
  QString resp = r.reachable() ? QString::fromUtf8(r.body).simplified() : r.error;
  if (r.path == QLatin1String("/sequence") && r.json.isObject()) {
    int ok = 0, n = 0;
    for (const auto& s : r.object().value(QStringLiteral("steps")).toArray()) {
      ++n;
      ok += s.toObject().value(QStringLiteral("ok")).toBool() ? 1 : 0;
    }
    resp = tr("%1/%2 steps ok  ·  %3").arg(ok).arg(n).arg(resp);
  }
  it->setText(4, resp.left(400));
  it->setToolTip(4, prettyJson(r.body).left(4000));
  const ThemeColors& c = Theme::colors();
  it->setForeground(2, r.ok() ? c.success : r.reachable() ? c.warning : c.danger);
  it->setForeground(0, c.faint);
  it->setForeground(3, c.faint);
  log_->insertTopLevelItem(0, it);
  while (log_->topLevelItemCount() > 500) delete log_->takeTopLevelItem(log_->topLevelItemCount() - 1);
}

void ControlPage::showEvent(QShowEvent* e) {
  QSignalBlocker b(confirm_);
  confirm_->setChecked(cfg::get(cfg::kConfirm).toBool());
  QWidget::showEvent(e);
}
