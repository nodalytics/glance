// glance-admin — Qt6 desktop admin client of the glance HTTP API.
//
//   glance-admin [--url http://host:8080] [--theme dark|light|system]
//                [--page overview|table|capture|cards|control|inspector|settings]
//                [--demo] [--no-connect] [--screenshot <dir> [--live]]

#include <QApplication>
#include <QCommandLineParser>
#include <QDir>
#include <QEventLoop>
#include <QFont>
#include <QFontDatabase>
#include <QSettings>
#include <QTimer>

#include <cstdio>

#include "demo.h"
#include "mainwindow.h"
#include "pages.h"
#include "theme.h"

namespace {

void settle() {
  for (int i = 0; i < 6; ++i) QCoreApplication::processEvents(QEventLoop::AllEvents, 30);
}

// Grab every page (dark, then light) as PNGs — a design check that works
// headless with QT_QPA_PLATFORM=offscreen.
int screenshots(MainWindow& w, const QString& dir) {
  QDir().mkpath(dir);
  int saved = 0;
  for (const char* theme : {"dark", "light"}) {
    Theme::instance().apply(QString::fromLatin1(theme));
    for (int i = 0; i < w.pageCount(); ++i) {
      w.showPage(i);
      settle();
      const QString path =
          QDir(dir).filePath(QStringLiteral("%1-%2-%3.png").arg(i + 1, 2, 10, QLatin1Char('0')).arg(w.pageKey(i), QString::fromLatin1(theme)));
      if (w.grab().save(path)) {
        std::fprintf(stdout, "%s\n", qPrintable(path));
        ++saved;
      }
    }
  }
  return saved > 0 ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  QApplication app(argc, argv);
  QApplication::setOrganizationName(QStringLiteral("glance"));
  QApplication::setApplicationName(QStringLiteral("glance-admin"));
  QApplication::setApplicationVersion(QStringLiteral(GLANCE_ADMIN_VERSION));
  QApplication::setStyle(QStringLiteral("Fusion"));

  QCommandLineParser cli;
  cli.setApplicationDescription(QStringLiteral("Desktop admin client of the glance HTTP API."));
  cli.addHelpOption();
  cli.addVersionOption();
  QCommandLineOption urlOpt(QStringLiteral("url"), QStringLiteral("glance-server base URL."), QStringLiteral("url"));
  QCommandLineOption themeOpt(QStringLiteral("theme"), QStringLiteral("dark, light or system."), QStringLiteral("name"));
  QCommandLineOption pageOpt(QStringLiteral("page"), QStringLiteral("Start page key."), QStringLiteral("key"));
  QCommandLineOption demoOpt(QStringLiteral("demo"), QStringLiteral("Fill the pages with sample data; no server."));
  QCommandLineOption noConnOpt(QStringLiteral("no-connect"), QStringLiteral("Do not connect on start-up."));
  QCommandLineOption shotOpt(QStringLiteral("screenshot"),
                             QStringLiteral("Save a PNG of every page (dark + light) into <dir> and exit."),
                             QStringLiteral("dir"));
  QCommandLineOption liveOpt(QStringLiteral("live"),
                             QStringLiteral("With --screenshot: connect to the server instead of using demo data."));
  cli.addOptions({urlOpt, themeOpt, pageOpt, demoOpt, noConnOpt, shotOpt, liveOpt});
  cli.process(app);

  QFont f = QApplication::font();
  f.setFamilies({QStringLiteral("Inter"), QStringLiteral("Cantarell"), QStringLiteral("Noto Sans"),
                 QStringLiteral("Segoe UI"), QStringLiteral("DejaVu Sans")});
  f.setPixelSize(13);
  f.setHintingPreference(QFont::PreferNoHinting);
  QApplication::setFont(f);

  if (cli.isSet(urlOpt)) cfg::set(cfg::kUrl, cli.value(urlOpt));
  const QString theme = cli.isSet(themeOpt) ? cli.value(themeOpt) : cfg::get(cfg::kTheme).toString();
  Theme::instance().apply(theme);

  MainWindow w;
  const bool shots = cli.isSet(shotOpt);
  const bool live = shots && cli.isSet(liveOpt);
  if (cli.isSet(demoOpt) || (shots && !live)) loadDemo(w);
  if (cli.isSet(pageOpt) && !w.showPage(cli.value(pageOpt)))
    std::fprintf(stderr, "unknown page '%s'\n", qPrintable(cli.value(pageOpt)));
  w.show();

  if (shots) {
    w.resize(1440, 900);
    if (live) {
      // Let a few polls land: connect, health, info, state.
      w.connectToServer(true);
      QEventLoop loop;
      QTimer::singleShot(2500, &loop, &QEventLoop::quit);
      loop.exec();
    }
    settle();
    return screenshots(w, cli.value(shotOpt));
  }
  if (!cli.isSet(demoOpt) && !cli.isSet(noConnOpt) && cfg::get(cfg::kAutoConnect).toBool())
    QTimer::singleShot(0, &w, [&w] { w.connectToServer(true); });
  return app.exec();
}
