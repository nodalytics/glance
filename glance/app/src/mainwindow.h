#pragma once

#include <QMainWindow>
#include <QVector>

#include "apiclient.h"

class QLabel;
class QLineEdit;
class QPushButton;
class QStackedWidget;
class QTimer;
class Pill;
class OverviewPage;
class TablePage;
class CapturePage;
class CardLabPage;
class ControlPage;
class InspectorPage;
class SettingsPage;

class MainWindow : public QMainWindow {
  Q_OBJECT
 public:
  explicit MainWindow(QWidget* parent = nullptr);
  ~MainWindow() override;

  ApiClient* api() { return api_; }
  int pageCount() const;
  QString pageKey(int i) const;  // "overview", "table", ...
  void showPage(int i);
  bool showPage(const QString& key);
  void setDemoMode();
  void connectToServer(bool on);

  OverviewPage* overview() { return overview_; }
  TablePage* table() { return table_; }
  CapturePage* capture() { return capture_; }
  CardLabPage* cardLab() { return cardLab_; }
  ControlPage* control() { return control_; }
  InspectorPage* inspector() { return inspector_; }
  // Surface health in the top bar as if a /health poll had come back.
  void showHealth(const ApiResult& r);

 private:
  QWidget* buildSidebar();
  QWidget* buildTopBar();
  void refreshIcons();
  void pollHealth();
  void fetchInfo();
  void onInfo(const ApiResult& r);
  void setOnline(bool online);
  void applyPolling();
  void onExchange(const ApiResult& r);

  ApiClient* api_;
  QLineEdit* url_;
  QPushButton* connect_;
  Pill* health_;
  QLabel* meta_;
  QPushButton* themeBtn_;
  QStackedWidget* stack_;
  QVector<QPushButton*> nav_;
  QLabel* footer_;
  QTimer* healthTimer_;
  bool connected_ = false;
  bool online_ = false;
  bool healthInFlight_ = false;
  bool demo_ = false;
  int healthTicks_ = 0;
  int requests_ = 0;

  OverviewPage* overview_;
  TablePage* table_;
  CapturePage* capture_;
  CardLabPage* cardLab_;
  ControlPage* control_;
  InspectorPage* inspector_;
  SettingsPage* settings_;
};
