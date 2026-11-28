#pragma once

// The admin app's pages. Each page owns its widgets and talks to the server
// through the shared ApiClient; MainWindow wires cross-page signals.

#include <QHash>
#include <QJsonObject>
#include <QPoint>
#include <QSettings>
#include <QVector>
#include <QWidget>

#include "apiclient.h"
#include "widgets.h"

class QCheckBox;
class QComboBox;
class QGridLayout;
class QLabel;
class QLineEdit;
class QPlainTextEdit;
class QPushButton;
class QSpinBox;
class QStackedWidget;
class QTabWidget;
class QTimer;
class QTreeWidget;
class QVBoxLayout;
class CardWidget;
class DropZone;
class ImageView;
class Pill;
class ScoreBar;
class Sparkline;
class TableView;

// Persisted settings keys + defaults (QSettings "glance"/"glance-admin").
namespace cfg {
inline constexpr const char* kUrl = "server/url";
inline constexpr const char* kHealthMs = "poll/health_ms";
inline constexpr const char* kStateMs = "poll/state_ms";
inline constexpr const char* kStateLive = "poll/state_live";
inline constexpr const char* kTimeoutMs = "net/timeout_ms";
inline constexpr const char* kTheme = "ui/theme";
inline constexpr const char* kConfirm = "control/confirm";
inline constexpr const char* kAutoFrame = "capture/auto_frame";
inline constexpr const char* kAutoConnect = "server/auto_connect";
inline constexpr const char* kHistory = "inspector/history";
QVariant get(const char* key);
void set(const char* key, const QVariant& v);
}  // namespace cfg

// Wrap a page body in a scroll area with standard margins.
QWidget* scrollPage(QWidget* body);

// ---------------------------------------------------------------- Overview
class OverviewPage : public QWidget {
  Q_OBJECT
 public:
  explicit OverviewPage(ApiClient* api, QWidget* parent = nullptr);
  void onHealth(const ApiResult& r);
  void onInfo(const ApiResult& r);
  void setConnected(bool on);

 private:
  struct Tile {
    QLabel* value;
    QLabel* detail;
    Pill* pill;
  };
  Tile addTile(QGridLayout* grid, int row, int col, const QString& title);

  ApiClient* api_;
  Tile server_, ocr_, control_, mapping_, vision_, latency_;
  Sparkline* spark_;
  QLabel* sparkStats_;
  QLabel* endpoints_;
  QVector<double> samples_;
  QTreeWidget* infoTree_;
};

// ---------------------------------------------------------------- Live table
class TablePage : public QWidget {
  Q_OBJECT
 public:
  explicit TablePage(ApiClient* api, QWidget* parent = nullptr);
  void setConnected(bool on);
  void applyState(const QJsonObject& state);
  void applyIntervalFromSettings();

 public Q_SLOTS:
  void refresh();

 private:
  void onResult(const ApiResult& r);
  void updateTimer();
  void setRow(QLabel* l, const QString& v);

  ApiClient* api_;
  TableView* table_;
  QTimer* timer_;
  QPushButton* live_;
  QSpinBox* interval_;
  Pill* status_;
  QLabel* updated_;
  QLabel *stage_, *pot_, *call_, *raise_, *dealer_, *board_, *hero_;
  Pill* turn_;
  Pill* valid_;
  QVBoxLayout* issues_;
  QWidget* issuesBox_;
  QByteArray lastValidation_;
  bool connected_ = false;
  bool inFlight_ = false;
};

// ---------------------------------------------------------------- Capture
class CapturePage : public QWidget {
  Q_OBJECT
 public:
  explicit CapturePage(ApiClient* api, QWidget* parent = nullptr);
  void setFrameImage(const QImage& img, const QString& caption);  // demo / grab
  void setCaptureResult(Tone tone, const QString& pill, const QString& text);
  void setScreenshot(const QByteArray& bytes, const QString& name);

 public Q_SLOTS:
  void refreshFrame();
  void send();

 Q_SIGNALS:
  void stateReceived(const QJsonObject& state);
  void pointPicked(QPoint p);

 private:
  ApiClient* api_;
  DropZone* drop_;
  QPushButton* sendBtn_;
  Pill* result_;
  QLabel* resultText_;
  ImageView* frame_;
  Pill* frameStatus_;
  QLabel* frameCaption_;
};

// ---------------------------------------------------------------- Card lab
class CardLabPage : public QWidget {
  Q_OBJECT
 public:
  explicit CardLabPage(ApiClient* api, QWidget* parent = nullptr);
  void applyReading(const QJsonObject& r);
  void setCrop(const QByteArray& png, const QString& name);

 public Q_SLOTS:
  void recognize();

 private:
  ApiClient* api_;
  DropZone* drop_;
  QComboBox* slot_;
  QPushButton* run_;
  QLabel* banner_;
  CardWidget* card_;
  QLabel* headline_;
  QLabel* subline_;
  Pill *verification_, *occupancy_, *color_;
  QLabel *rank_, *rankConf_, *rankMargin_, *rankSrc_;
  QLabel *suit_, *suitConf_, *suitMargin_, *suitSrc_;
  QVBoxLayout* suitBars_;
  QWidget* suitBox_;
  ScoreBar *white_, *green_, *edge_, *bright_, *bstd_;
  QLabel* occReason_;
};

// ---------------------------------------------------------------- Control
class ControlPage : public QWidget {
  Q_OBJECT
 public:
  explicit ControlPage(ApiClient* api, QWidget* parent = nullptr);
  void setBackend(const QString& backend);
  void setActions(const QStringList& names);
  void setClickPoint(QPoint p);
  void logResult(const ApiResult& r);

 Q_SIGNALS:
  void stateReceived(const QJsonObject& state);
  void grabbed();

 protected:
  void showEvent(QShowEvent* e) override;

 private:
  bool confirm(const QString& what);
  void post(const QString& path, const QJsonDocument& body, bool input, const QString& what);
  void rebuildActions();

  ApiClient* api_;
  QCheckBox* confirm_;
  Pill* backend_;
  QLabel* backendNote_;
  QComboBox* grabMode_;
  QLineEdit* grabTitle_;
  QSpinBox *gx_, *gy_, *gw_, *gh_;
  QStackedWidget* grabStack_;
  QWidget* actionsBox_;
  QGridLayout* actionsGrid_;
  QStringList actions_;
  QComboBox* target_;
  QSpinBox *cx_, *cy_;
  QComboBox* button_;
  QLineEdit* keysym_;
  QLineEdit* text_;
  QPlainTextEdit* sequence_;
  QLabel* seqStatus_;
  QTreeWidget* log_;
};

// ---------------------------------------------------------------- Inspector
class InspectorPage : public QWidget {
  Q_OBJECT
 public:
  explicit InspectorPage(QWidget* parent = nullptr);
  void record(const ApiResult& r);

 protected:
  void showEvent(QShowEvent* e) override;

 private:
  void show(int row);
  void rebuildList();

  QVector<ApiResult> items_;
  QTreeWidget* list_;
  QLineEdit* filter_;
  QCheckBox* showPolls_;
  QLabel* head_;
  Pill* status_;
  QTabWidget* tabs_;
  QTreeWidget* tree_;
  QPlainTextEdit* raw_;
  QPlainTextEdit* request_;
  ImageView* image_;
  int current_ = -1;
};

// ---------------------------------------------------------------- Settings
class SettingsPage : public QWidget {
  Q_OBJECT
 public:
  explicit SettingsPage(QWidget* parent = nullptr);

 Q_SIGNALS:
  void themeChanged(const QString& name);
  void pollingChanged();

 protected:
  void showEvent(QShowEvent* e) override;

 private:
  QComboBox* theme_;
  QSpinBox *health_, *state_, *timeout_;
  QCheckBox *confirm_, *autoFrame_, *autoConnect_;
};
