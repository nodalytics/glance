#include "mainwindow.h"

#include <QApplication>
#include <QCloseEvent>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QPainter>
#include <QPainterPath>
#include <QPushButton>
#include <QShortcut>
#include <QStackedWidget>
#include <QStatusBar>
#include <QTimer>
#include <QVBoxLayout>

#include "pages.h"
#include "theme.h"
#include "widgets.h"

namespace {

struct NavEntry {
  const char* key;
  const char* label;
};
constexpr NavEntry kNav[] = {{"overview", "Overview"}, {"table", "Live table"}, {"capture", "Capture"},
                             {"cards", "Card lab"},     {"control", "Control"},  {"inspector", "Inspector"},
                             {"settings", "Settings"}};

// Small line icons painted at runtime so the app ships no image assets.
QPixmap navPixmap(int kind, const QColor& col, qreal dpr) {
  const int s = 18;
  QPixmap pm(QSize(s, s) * dpr);
  pm.setDevicePixelRatio(dpr);
  pm.fill(Qt::transparent);
  QPainter p(&pm);
  p.setRenderHint(QPainter::Antialiasing);
  QPen pen(col, 1.6, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin);
  p.setPen(pen);
  p.setBrush(Qt::NoBrush);
  switch (kind) {
    case 0:  // overview: 2x2 tiles
      p.drawRoundedRect(QRectF(2.5, 2.5, 5.5, 5.5), 1.6, 1.6);
      p.drawRoundedRect(QRectF(10, 2.5, 5.5, 5.5), 1.6, 1.6);
      p.drawRoundedRect(QRectF(2.5, 10, 5.5, 5.5), 1.6, 1.6);
      p.drawRoundedRect(QRectF(10, 10, 5.5, 5.5), 1.6, 1.6);
      break;
    case 1:  // table: stadium + chip
      p.drawRoundedRect(QRectF(1.5, 4.5, 15, 9), 4.5, 4.5);
      p.drawEllipse(QPointF(9, 9), 1.8, 1.8);
      break;
    case 2: {  // capture: viewfinder
      const qreal a = 2.5, b = 15.5, l = 4;
      p.drawLine(QPointF(a, a + l), QPointF(a, a));
      p.drawLine(QPointF(a, a), QPointF(a + l, a));
      p.drawLine(QPointF(b - l, a), QPointF(b, a));
      p.drawLine(QPointF(b, a), QPointF(b, a + l));
      p.drawLine(QPointF(a, b - l), QPointF(a, b));
      p.drawLine(QPointF(a, b), QPointF(a + l, b));
      p.drawLine(QPointF(b - l, b), QPointF(b, b));
      p.drawLine(QPointF(b, b), QPointF(b, b - l));
      p.drawEllipse(QPointF(9, 9), 2.6, 2.6);
      break;
    }
    case 3:  // card lab: two cards
      p.save();
      p.translate(7, 9);
      p.rotate(-12);
      p.drawRoundedRect(QRectF(-4, -6, 8, 12), 1.6, 1.6);
      p.restore();
      p.save();
      p.translate(11.5, 9.5);
      p.rotate(10);
      p.setBrush(col);
      p.drawRoundedRect(QRectF(-4, -6, 8, 12), 1.6, 1.6);
      p.restore();
      break;
    case 4: {  // control: cursor
      QPainterPath path;
      path.moveTo(4, 2.5);
      path.lineTo(4, 14.5);
      path.lineTo(7.2, 11.4);
      path.lineTo(9.6, 16);
      path.lineTo(11.6, 15);
      path.lineTo(9.3, 10.6);
      path.lineTo(13.6, 10.4);
      path.closeSubpath();
      p.drawPath(path);
      break;
    }
    case 5: {  // inspector: braces
      QPainterPath l;
      l.moveTo(6.5, 2.5);
      l.cubicTo(3.5, 2.5, 5.5, 8, 2.5, 9);
      l.cubicTo(5.5, 10, 3.5, 15.5, 6.5, 15.5);
      QPainterPath r;
      r.moveTo(11.5, 2.5);
      r.cubicTo(14.5, 2.5, 12.5, 8, 15.5, 9);
      r.cubicTo(12.5, 10, 14.5, 15.5, 11.5, 15.5);
      p.drawPath(l);
      p.drawPath(r);
      break;
    }
    default: {  // settings: sliders
      p.drawLine(QPointF(2.5, 5), QPointF(15.5, 5));
      p.drawLine(QPointF(2.5, 13), QPointF(15.5, 13));
      p.setBrush(col);
      p.drawEllipse(QPointF(6, 5), 2.2, 2.2);
      p.drawEllipse(QPointF(12, 13), 2.2, 2.2);
      break;
    }
  }
  return pm;
}

}  // namespace

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
  setWindowTitle(tr("glance admin"));
  api_ = new ApiClient(this);
  api_->setTimeoutMs(cfg::get(cfg::kTimeoutMs).toInt());
  healthTimer_ = new QTimer(this);
  connect(healthTimer_, &QTimer::timeout, this, &MainWindow::pollHealth);

  overview_ = new OverviewPage(api_);
  table_ = new TablePage(api_);
  capture_ = new CapturePage(api_);
  cardLab_ = new CardLabPage(api_);
  control_ = new ControlPage(api_);
  inspector_ = new InspectorPage;
  settings_ = new SettingsPage;

  auto* root = new QWidget;
  root->setObjectName(QStringLiteral("Root"));
  auto* h = new QHBoxLayout(root);
  h->setContentsMargins(0, 0, 0, 0);
  h->setSpacing(0);
  h->addWidget(buildSidebar());
  auto* right = new QVBoxLayout;
  right->setContentsMargins(0, 0, 0, 0);
  right->setSpacing(0);
  right->addWidget(buildTopBar());
  stack_ = new QStackedWidget;
  stack_->setObjectName(QStringLiteral("MainStack"));
  for (QWidget* w : std::initializer_list<QWidget*>{overview_, table_, capture_, cardLab_, control_, inspector_, settings_})
    stack_->addWidget(w);
  right->addWidget(stack_, 1);
  h->addLayout(right, 1);
  setCentralWidget(root);

  footer_ = new QLabel;
  footer_->setContentsMargins(0, 0, 14, 0);
  statusBar()->addPermanentWidget(footer_);
  statusBar()->setSizeGripEnabled(false);

  connect(api_, &ApiClient::exchanged, this, &MainWindow::onExchange);
  connect(capture_, &CapturePage::stateReceived, table_, &TablePage::applyState);
  connect(control_, &ControlPage::stateReceived, table_, &TablePage::applyState);
  connect(control_, &ControlPage::grabbed, capture_, [this] {
    if (cfg::get(cfg::kAutoFrame).toBool()) capture_->refreshFrame();
  });
  connect(capture_, &CapturePage::pointPicked, this, [this](QPoint p) {
    control_->setClickPoint(p);
    statusBar()->showMessage(tr("Click point %1, %2 set on the Control page").arg(p.x()).arg(p.y()), 4000);
  });
  connect(settings_, &SettingsPage::themeChanged, this, [this](const QString& t) {
    Theme::instance().apply(t);
  });
  connect(settings_, &SettingsPage::pollingChanged, this, &MainWindow::applyPolling);
  connect(&Theme::instance(), &Theme::changed, this, &MainWindow::refreshIcons);

  for (int i = 0; i < pageCount(); ++i) {
    auto* sc = new QShortcut(QKeySequence(Qt::CTRL | Qt::Key(Qt::Key_1 + i)), this);
    connect(sc, &QShortcut::activated, this, [this, i] { showPage(i); });
  }
  auto* refresh = new QShortcut(QKeySequence::Refresh, this);
  connect(refresh, &QShortcut::activated, table_, &TablePage::refresh);

  refreshIcons();
  showPage(0);
  resize(1360, 860);
  setMinimumSize(1080, 700);
}

MainWindow::~MainWindow() = default;

QWidget* MainWindow::buildSidebar() {
  auto* side = new QWidget;
  side->setObjectName(QStringLiteral("Sidebar"));
  side->setAttribute(Qt::WA_StyledBackground);
  side->setFixedWidth(212);
  auto* v = new QVBoxLayout(side);
  v->setContentsMargins(14, 18, 14, 14);
  v->setSpacing(4);

  auto* brand = new QHBoxLayout;
  brand->setSpacing(10);
  auto* logo = new QLabel;
  {
    const qreal dpr = 2.0;
    QPixmap pm(QSize(30, 30) * dpr);
    pm.setDevicePixelRatio(dpr);
    pm.fill(Qt::transparent);
    QPainter p(&pm);
    p.setRenderHint(QPainter::Antialiasing);
    QLinearGradient g(0, 0, 30, 30);
    g.setColorAt(0, QColor(0x7d, 0x9a, 0xff));
    g.setColorAt(1, QColor(0x3c, 0xcf, 0x91));
    p.setPen(Qt::NoPen);
    p.setBrush(g);
    p.drawRoundedRect(QRectF(0, 0, 30, 30), 8, 8);
    p.setBrush(Qt::NoBrush);
    p.setPen(QPen(Qt::white, 2.2));
    p.drawEllipse(QPointF(15, 15), 7.5, 5);  // an eye: "glance"
    p.setBrush(Qt::white);
    p.drawEllipse(QPointF(15, 15), 2.2, 2.2);
    logo->setPixmap(pm);
  }
  brand->addWidget(logo);
  auto* names = new QVBoxLayout;
  names->setSpacing(0);
  auto* b1 = new QLabel(QStringLiteral("glance"));
  b1->setObjectName(QStringLiteral("Brand"));
  auto* b2 = new QLabel(QStringLiteral("ADMIN CONSOLE"));
  b2->setObjectName(QStringLiteral("BrandSub"));
  names->addWidget(b1);
  names->addWidget(b2);
  brand->addLayout(names, 1);
  v->addLayout(brand);
  v->addSpacing(22);
  v->addWidget(makeLabel(tr("WORKSPACE"), "section"));
  v->addSpacing(4);

  for (int i = 0; i < pageCount(); ++i) {
    if (i == 4) {
      v->addSpacing(14);
      v->addWidget(makeLabel(tr("ADMIN"), "section"));
      v->addSpacing(4);
    }
    auto* b = new QPushButton(tr(kNav[i].label));
    b->setObjectName(QStringLiteral("NavButton"));
    b->setCheckable(true);
    b->setAutoExclusive(true);
    b->setIconSize(QSize(18, 18));
    b->setCursor(Qt::PointingHandCursor);
    b->setToolTip(tr("%1  (Ctrl+%2)").arg(tr(kNav[i].label)).arg(i + 1));
    connect(b, &QPushButton::clicked, this, [this, i] { showPage(i); });
    nav_.push_back(b);
    v->addWidget(b);
  }
  v->addStretch();
  auto* ver = makeLabel(tr("v%1  ·  Qt %2").arg(QStringLiteral(GLANCE_ADMIN_VERSION), QString::fromLatin1(qVersion())),
                        "faint");
  v->addWidget(ver);
  return side;
}

QWidget* MainWindow::buildTopBar() {
  auto* bar = new QWidget;
  bar->setObjectName(QStringLiteral("TopBar"));
  bar->setAttribute(Qt::WA_StyledBackground);
  auto* h = new QHBoxLayout(bar);
  h->setContentsMargins(28, 12, 20, 12);
  h->setSpacing(10);
  url_ = new QLineEdit(cfg::get(cfg::kUrl).toString());
  url_->setObjectName(QStringLiteral("UrlEdit"));
  url_->setPlaceholderText(QStringLiteral("http://127.0.0.1:8080"));
  url_->setToolTip(tr("glance-server base URL"));
  connect_ = new QPushButton(tr("Connect"));
  connect_->setProperty("kind", "primary");
  connect_->setMinimumWidth(104);
  health_ = new Pill(tr("Disconnected"), Tone::Neutral);
  meta_ = makeLabel(QString(), "faint");
  themeBtn_ = new QPushButton;
  themeBtn_->setProperty("kind", "ghost");
  themeBtn_->setToolTip(tr("Toggle dark / light theme"));
  themeBtn_->setFixedWidth(40);
  h->addWidget(url_);
  h->addWidget(connect_);
  h->addSpacing(6);
  h->addWidget(health_);
  h->addWidget(meta_, 1);
  h->addWidget(themeBtn_);

  connect(connect_, &QPushButton::clicked, this, [this] { connectToServer(!connected_); });
  connect(url_, &QLineEdit::returnPressed, this, [this] {
    connectToServer(false);
    connectToServer(true);
  });
  connect(themeBtn_, &QPushButton::clicked, this, [] {
    const QString next = Theme::mode() == Theme::Mode::Dark ? QStringLiteral("light") : QStringLiteral("dark");
    cfg::set(cfg::kTheme, next);
    Theme::instance().apply(next);
  });
  return bar;
}

void MainWindow::refreshIcons() {
  const ThemeColors& c = Theme::colors();
  const qreal dpr = std::max<qreal>(2.0, devicePixelRatioF());
  for (int i = 0; i < nav_.size(); ++i) {
    QIcon icon;
    icon.addPixmap(navPixmap(i, c.muted, dpr), QIcon::Normal, QIcon::Off);
    icon.addPixmap(navPixmap(i, c.accent, dpr), QIcon::Normal, QIcon::On);
    icon.addPixmap(navPixmap(i, c.accent, dpr), QIcon::Active, QIcon::On);
    nav_[i]->setIcon(icon);
  }
  // Moon in dark mode (switch to light), sun in light mode.
  QPixmap pm(QSize(18, 18) * dpr);
  pm.setDevicePixelRatio(dpr);
  pm.fill(Qt::transparent);
  QPainter p(&pm);
  p.setRenderHint(QPainter::Antialiasing);
  p.setPen(QPen(c.muted, 1.6, Qt::SolidLine, Qt::RoundCap));
  if (Theme::mode() == Theme::Mode::Dark) {
    QPainterPath moon, cut;
    moon.addEllipse(QPointF(9, 9), 6.5, 6.5);
    cut.addEllipse(QPointF(12.5, 6), 5.5, 5.5);
    p.drawPath(moon.subtracted(cut));
  } else {
    p.drawEllipse(QPointF(9, 9), 3.4, 3.4);
    for (int k = 0; k < 8; ++k) {
      p.save();
      p.translate(9, 9);
      p.rotate(k * 45);
      p.drawLine(QPointF(0, 5.6), QPointF(0, 7.6));
      p.restore();
    }
  }
  p.end();
  themeBtn_->setIcon(QIcon(pm));
}

int MainWindow::pageCount() const { return int(std::size(kNav)); }

QString MainWindow::pageKey(int i) const { return QString::fromLatin1(kNav[i].key); }

void MainWindow::showPage(int i) {
  if (i < 0 || i >= pageCount()) return;
  stack_->setCurrentIndex(i);
  nav_[i]->setChecked(true);
}

bool MainWindow::showPage(const QString& key) {
  for (int i = 0; i < pageCount(); ++i) {
    if (pageKey(i) == key) {
      showPage(i);
      return true;
    }
  }
  return false;
}

void MainWindow::connectToServer(bool on) {
  if (demo_) return;
  connected_ = on;
  healthTicks_ = 0;
  if (on) {
    QString u = url_->text().trimmed();
    if (u.isEmpty()) u = QStringLiteral("http://127.0.0.1:8080");
    api_->setBaseUrl(QUrl::fromUserInput(u));
    url_->setText(api_->baseUrl().toString());
    cfg::set(cfg::kUrl, url_->text());
    connect_->setText(tr("Disconnect"));
    connect_->setProperty("kind", "");
    repolish(connect_);
    health_->set(tr("Connecting…"), Tone::Accent);
    applyPolling();
    pollHealth();
  } else {
    healthTimer_->stop();
    connect_->setText(tr("Connect"));
    connect_->setProperty("kind", "primary");
    repolish(connect_);
    health_->set(tr("Disconnected"), Tone::Neutral);
    meta_->clear();
    setOnline(false);
    overview_->setConnected(false);
  }
}

void MainWindow::applyPolling() {
  api_->setTimeoutMs(cfg::get(cfg::kTimeoutMs).toInt());
  healthTimer_->setInterval(cfg::get(cfg::kHealthMs).toInt());
  table_->applyIntervalFromSettings();
  if (connected_) healthTimer_->start();
}

void MainWindow::pollHealth() {
  if (!connected_ || healthInFlight_) return;
  healthInFlight_ = true;
  api_->get(QStringLiteral("/health"), [this](const ApiResult& r) {
    healthInFlight_ = false;
    if (!connected_) return;
    showHealth(r);
    overview_->onHealth(r);
    ++healthTicks_;
    if (r.ok() && (!online_ || healthTicks_ % 15 == 1)) fetchInfo();
    setOnline(r.ok());
  }, true);
}

void MainWindow::showHealth(const ApiResult& r) {
  if (r.ok()) {
    health_->set(tr("Online · %1 ms").arg(r.elapsedMs), Tone::Success);
    const QString backend =
        r.object().value(QStringLiteral("control")).toObject().value(QStringLiteral("backend")).toString();
    control_->setBackend(backend);
  } else {
    health_->set(r.reachable() ? tr("Error %1").arg(r.status) : tr("Offline"), Tone::Danger);
    health_->setToolTip(r.error);
  }
}

void MainWindow::fetchInfo() {
  api_->get(QStringLiteral("/info"), [this](const ApiResult& r) { onInfo(r); }, true);
}

void MainWindow::onInfo(const ApiResult& r) {
  overview_->onInfo(r);
  if (!r.ok()) {
    if (r.status == 404) meta_->setText(tr("server has no /info"));
    return;
  }
  const QJsonObject o = r.object();
  QStringList bits;
  const QString name = o.value(QStringLiteral("name")).toString(QStringLiteral("glance"));
  const QString ver = o.value(QStringLiteral("version")).toString();
  bits << (ver.isEmpty() ? name : name + QLatin1Char(' ') + ver);
  const QJsonValue mp = o.value(QStringLiteral("mapping"));
  const QString mname = mp.isString() ? mp.toString() : mp.toObject().value(QStringLiteral("name")).toString();
  if (!mname.isEmpty()) bits << mname;
  meta_->setText(bits.join(QStringLiteral("  ·  ")));

  // Named actions, when the server lists them (mapping.actions or actions).
  QJsonValue acts = mp.toObject().value(QStringLiteral("actions"));
  if (acts.isUndefined()) acts = o.value(QStringLiteral("actions"));
  QStringList names;
  if (acts.isObject()) names = acts.toObject().keys();
  for (const auto& a : acts.toArray()) {
    if (a.isString()) names << a.toString();
    else if (a.isObject()) names << a.toObject().value(QStringLiteral("name")).toString();
  }
  names.removeAll(QString());
  if (!names.isEmpty()) control_->setActions(names);
}

void MainWindow::setOnline(bool online) {
  if (online == online_) return;
  online_ = online;
  table_->setConnected(online);
  if (online) capture_->refreshFrame();  // also reveals a missing /frame.png route
}

void MainWindow::setDemoMode() {
  demo_ = true;
  healthTimer_->stop();
  connect_->setText(tr("Demo"));
  connect_->setEnabled(false);
  url_->setEnabled(false);
}

void MainWindow::onExchange(const ApiResult& r) {
  ++requests_;
  inspector_->record(r);
  footer_->setText(tr("%1 requests  ·  last %2 %3 → %4 in %5 ms")
                       .arg(requests_)
                       .arg(r.method, r.path, r.reachable() ? QString::number(r.status) : tr("offline"))
                       .arg(r.elapsedMs));
}
