#include <QGridLayout>
#include <QHeaderView>
#include <QJsonArray>
#include <QLabel>
#include <QScrollArea>
#include <QTreeWidget>
#include <QVBoxLayout>

#include <cmath>
#include <limits>

#include "pages.h"
#include "widgets.h"

// ---------------------------------------------------------------- cfg

namespace cfg {

namespace {
QVariant fallback(const QString& k) {
  if (k == QLatin1String(kUrl)) return QStringLiteral("http://127.0.0.1:8080");
  if (k == QLatin1String(kHealthMs)) return 2000;
  if (k == QLatin1String(kStateMs)) return 1000;
  if (k == QLatin1String(kStateLive)) return true;
  if (k == QLatin1String(kTimeoutMs)) return 4000;
  if (k == QLatin1String(kTheme)) return QStringLiteral("dark");
  if (k == QLatin1String(kConfirm)) return true;
  if (k == QLatin1String(kAutoFrame)) return true;
  if (k == QLatin1String(kAutoConnect)) return true;
  if (k == QLatin1String(kHistory)) return 300;
  return {};
}
}  // namespace

QVariant get(const char* key) {
  QSettings s;
  return s.value(QLatin1String(key), fallback(QLatin1String(key)));
}

void set(const char* key, const QVariant& v) {
  QSettings s;
  s.setValue(QLatin1String(key), v);
}

}  // namespace cfg

QWidget* scrollPage(QWidget* body) {
  auto* sa = new QScrollArea;
  sa->setWidgetResizable(true);
  sa->setFrameShape(QFrame::NoFrame);
  body->setObjectName(QStringLiteral("PageBody"));
  sa->setWidget(body);
  return sa;
}

// ---------------------------------------------------------------- Overview

OverviewPage::Tile OverviewPage::addTile(QGridLayout* grid, int row, int col, const QString& title) {
  QVBoxLayout* v = nullptr;
  QFrame* panel = makePanel(QString(), &v);
  v->setSpacing(6);
  auto* top = new QHBoxLayout;
  top->addWidget(makeLabel(title.toUpper(), "section"), 1);
  Tile t;
  t.pill = new Pill(tr("—"), Tone::Neutral);
  top->addWidget(t.pill);
  v->addLayout(top);
  t.value = makeLabel(QStringLiteral("—"), "metric");
  t.value->setTextInteractionFlags(Qt::TextSelectableByMouse);
  v->addWidget(t.value);
  t.detail = makeLabel(QString(), "muted");
  t.detail->setWordWrap(true);
  v->addWidget(t.detail);
  v->addStretch();
  panel->setMinimumHeight(126);
  grid->addWidget(panel, row, col);
  return t;
}

OverviewPage::OverviewPage(ApiClient* api, QWidget* parent) : QWidget(parent), api_(api) {
  auto* body = new QWidget;
  auto* v = new QVBoxLayout(body);
  v->setContentsMargins(28, 24, 28, 28);
  v->setSpacing(18);
  v->addWidget(makePageHeader(tr("Overview"),
                              tr("Server health, capabilities and the configured table skin.")));

  auto* grid = new QGridLayout;
  grid->setSpacing(16);
  server_ = addTile(grid, 0, 0, tr("Server"));
  latency_ = addTile(grid, 0, 1, tr("Latency"));
  control_ = addTile(grid, 0, 2, tr("Control backend"));
  ocr_ = addTile(grid, 1, 0, tr("OCR"));
  mapping_ = addTile(grid, 1, 1, tr("Mapping"));
  vision_ = addTile(grid, 1, 2, tr("Card vision"));
  for (int c = 0; c < 3; ++c) grid->setColumnStretch(c, 1);
  v->addLayout(grid);

  auto* row = new QHBoxLayout;
  row->setSpacing(16);
  QVBoxLayout* sv = nullptr;
  QFrame* sparkPanel = makePanel(tr("Health round-trip"), &sv);
  spark_ = new Sparkline;
  spark_->setMinimumHeight(110);
  sv->addWidget(spark_);
  sparkStats_ = makeLabel(tr("No samples yet"), "faint");
  sv->addWidget(sparkStats_);
  row->addWidget(sparkPanel, 3);

  QVBoxLayout* ev = nullptr;
  QFrame* epPanel = makePanel(tr("Endpoints"), &ev);
  endpoints_ = makeLabel(QString(), "mono");
  endpoints_->setTextFormat(Qt::RichText);
  endpoints_->setText(
      QStringLiteral("GET&nbsp;&nbsp;/health<br>GET&nbsp;&nbsp;/info<br>GET&nbsp;&nbsp;/state<br>"
                     "GET&nbsp;&nbsp;/frame.png<br>POST /capture<br>POST /recognize-card<br>"
                     "POST /grab · /click · /key · /sequence"));
  ev->addWidget(endpoints_);
  ev->addStretch();
  row->addWidget(epPanel, 2);
  v->addLayout(row);

  QVBoxLayout* iv = nullptr;
  QFrame* infoPanel = makePanel(tr("Server info  ·  GET /info"), &iv);
  infoTree_ = new QTreeWidget;
  infoTree_->setHeaderLabels({tr("Key"), tr("Value")});
  infoTree_->setProperty("mono", true);
  infoTree_->setRootIsDecorated(true);
  infoTree_->header()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
  infoTree_->setMinimumHeight(220);
  iv->addWidget(infoTree_);
  v->addWidget(infoPanel, 1);

  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  lay->addWidget(scrollPage(body));
  setConnected(false);
}

void OverviewPage::setConnected(bool on) {
  if (on) return;
  server_.pill->set(tr("Disconnected"), Tone::Neutral);
  server_.value->setText(QStringLiteral("—"));
  server_.detail->setText(tr("Press Connect to start polling /health."));
}

void OverviewPage::onHealth(const ApiResult& r) {
  samples_.push_back(r.ok() ? double(r.elapsedMs) : std::numeric_limits<double>::quiet_NaN());
  while (samples_.size() > 60) samples_.pop_front();
  spark_->push(samples_.back());
  double sum = 0, mx = 0;
  int n = 0, fails = 0;
  for (double s : samples_) {
    if (std::isnan(s)) {
      ++fails;
      continue;
    }
    sum += s;
    mx = std::max(mx, s);
    ++n;
  }
  sparkStats_->setText(n ? tr("avg %1 ms  ·  max %2 ms  ·  %3 failed of last %4")
                               .arg(sum / n, 0, 'f', 1)
                               .arg(mx, 0, 'f', 0)
                               .arg(fails)
                               .arg(samples_.size())
                         : tr("%1 failed samples").arg(fails));

  if (!r.ok()) {
    server_.pill->set(r.reachable() ? r.statusText() : tr("Offline"), Tone::Danger);
    server_.value->setText(tr("Unreachable"));
    server_.detail->setText(r.error.isEmpty() ? r.statusText() : r.error);
    latency_.pill->set(tr("Failing"), Tone::Danger);
    return;
  }
  const QJsonObject h = r.object();
  server_.pill->set(tr("Online"), Tone::Success);
  if (server_.value->text() == QStringLiteral("—") || server_.value->text() == tr("Unreachable"))
    server_.value->setText(h.value(QStringLiteral("status")).toString(QStringLiteral("ok")).toUpper());
  server_.detail->setText(api_->baseUrl().toString());
  latency_.value->setText(QStringLiteral("%1 ms").arg(r.elapsedMs));
  latency_.pill->set(r.elapsedMs < 50 ? tr("Fast") : r.elapsedMs < 250 ? tr("OK") : tr("Slow"),
                     r.elapsedMs < 50 ? Tone::Success : r.elapsedMs < 250 ? Tone::Accent : Tone::Warning);
  latency_.detail->setText(tr("GET /health round-trip"));

  const QJsonObject ctrl = h.value(QStringLiteral("control")).toObject();
  const QString backend = ctrl.value(QStringLiteral("backend")).toString();
  if (!backend.isEmpty()) {
    control_.value->setText(backend);
    const bool null = backend == QLatin1String("null");
    control_.pill->set(null ? tr("No input") : tr("Live input"), null ? Tone::Warning : Tone::Success);
    const QJsonObject win = ctrl.value(QStringLiteral("window")).toObject();
    control_.detail->setText(
        !win.isEmpty() ? tr("Window \"%1\" at %2, %3")
                             .arg(win.value(QStringLiteral("title")).toString())
                             .arg(win.value(QStringLiteral("x")).toInt())
                             .arg(win.value(QStringLiteral("y")).toInt())
        : null ? tr("Null backend: grabs fail and input is not injected.")
               : tr("Input space: last captured frame."));
  }
}

void OverviewPage::onInfo(const ApiResult& r) {
  if (!r.ok()) {
    const bool missing = r.status == 404;
    fillJsonTree(infoTree_, QJsonValue(QJsonValue::Undefined));
    if (missing) {
      server_.detail->setText(tr("%1  ·  server has no /info route (older build)").arg(api_->baseUrl().toString()));
    }
    for (Tile* t : {&ocr_, &mapping_, &vision_}) {
      t->pill->set(missing ? tr("Unknown") : tr("—"), Tone::Neutral);
      t->value->setText(QStringLiteral("—"));
      t->detail->setText(missing ? tr("Needs GET /info") : r.statusText());
    }
    return;
  }
  const QJsonObject o = r.object();
  fillJsonTree(infoTree_, o);
  const QString name = o.value(QStringLiteral("name")).toString(QStringLiteral("glance"));
  const QString ver = o.value(QStringLiteral("version")).toString();
  server_.value->setText(ver.isEmpty() ? name : QStringLiteral("%1 %2").arg(name, ver));

  const QJsonValue ocr = o.value(QStringLiteral("ocr_available"));
  if (ocr.isBool()) {
    ocr_.value->setText(ocr.toBool() ? tr("Available") : tr("Missing"));
    ocr_.pill->set(ocr.toBool() ? tr("tesseract") : tr("Numbers off"),
                   ocr.toBool() ? Tone::Success : Tone::Warning);
    ocr_.detail->setText(ocr.toBool() ? tr("Pot, stack and bet reads enabled.")
                                      : tr("Server built or running without tesseract: numeric fields are absent."));
  }

  // "control" may be a string or {"backend": ...}.
  const QJsonValue ctl = o.value(QStringLiteral("control"));
  const QString backend = ctl.isString() ? ctl.toString() : ctl.toObject().value(QStringLiteral("backend")).toString();
  if (!backend.isEmpty() && control_.value->text() == QStringLiteral("—")) control_.value->setText(backend);

  const QJsonValue mp = o.value(QStringLiteral("mapping"));
  QString mname = mp.isString() ? mp.toString() : mp.toObject().value(QStringLiteral("name")).toString();
  if (mname.isEmpty()) mname = o.value(QStringLiteral("mapping_name")).toString();
  mapping_.value->setText(mname.isEmpty() ? QStringLiteral("—") : mname);
  mapping_.pill->set(mname.isEmpty() ? tr("Unknown") : tr("Loaded"), mname.isEmpty() ? Tone::Neutral : Tone::Accent);
  const QJsonObject mo = mp.toObject();
  QStringList bits;
  if (mo.contains(QStringLiteral("max_players"))) bits << tr("%1 seats").arg(mo.value(QStringLiteral("max_players")).toInt());
  if (mo.contains(QStringLiteral("window_title")))
    bits << tr("window \"%1\"").arg(mo.value(QStringLiteral("window_title")).toString());
  const QJsonValue acts = mo.contains(QStringLiteral("actions")) ? mo.value(QStringLiteral("actions"))
                                                                 : o.value(QStringLiteral("actions"));
  const int nActs = acts.isArray() ? acts.toArray().size() : acts.toObject().size();
  if (nActs) bits << tr("%1 actions").arg(nActs);
  mapping_.detail->setText(bits.isEmpty() ? tr("Table skin served by this instance.") : bits.join(QStringLiteral("  ·  ")));

  const QJsonObject cv = o.value(QStringLiteral("card_vision")).toObject();
  if (cv.isEmpty()) {
    vision_.value->setText(QStringLiteral("—"));
    vision_.pill->set(tr("Unknown"), Tone::Neutral);
    vision_.detail->setText(tr("No card_vision block in /info."));
  } else {
    const bool on = cv.value(QStringLiteral("configured")).toBool();
    vision_.pill->set(on ? tr("Configured") : tr("Off"), on ? Tone::Success : Tone::Neutral);
    vision_.value->setText(on ? cv.value(QStringLiteral("profile")).toString(tr("enabled")) : tr("Not configured"));
    QStringList c;
    for (const char* k : {"suit_templates", "rank_templates"}) {
      const QJsonValue n = cv.value(QLatin1String(k));
      if (n.isDouble()) c << QStringLiteral("%1 %2").arg(n.toInt()).arg(QString::fromLatin1(k).section(QLatin1Char('_'), 0, 0));
    }
    const QJsonObject tc = cv.value(QStringLiteral("templates")).toObject();
    for (auto it = tc.begin(); it != tc.end(); ++it) c << QStringLiteral("%1 %2").arg(it.value().toInt()).arg(it.key());
    vision_.detail->setText(on ? (c.isEmpty() ? tr("POST /recognize-card ready.") : tr("Templates: %1").arg(c.join(QStringLiteral(", "))))
                               : tr("POST /recognize-card answers 409."));
  }
}
