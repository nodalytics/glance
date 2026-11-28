#pragma once

// Thin asynchronous client of the glance HTTP API (QtNetwork only).
//
// Every request completes through a callback with an ApiResult, and every
// result is also broadcast through exchanged() so the inspector and the
// activity log can observe traffic without the caller wiring them in.
// "quiet" requests are background polls (/health, /state): the inspector
// collapses them to the latest one per endpoint instead of logging each.

#include <QByteArray>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QObject>
#include <QString>
#include <QUrl>

#include <functional>

struct ApiResult {
  QString method;           // "GET" / "POST"
  QString path;             // "/state", "/recognize-card?slot=my1", ...
  QUrl url;
  QByteArray requestBody;   // JSON text, or empty for binary uploads
  QString requestSummary;   // human readable ("PNG image, 812 KB")
  int status = 0;           // HTTP status; 0 = no HTTP response at all
  QString error;            // transport error text (status 0) or server "error" field
  QByteArray body;
  QString contentType;
  QJsonDocument json;       // parsed body when it is JSON
  qint64 elapsedMs = 0;
  QDateTime when;
  bool quiet = false;

  bool ok() const { return status >= 200 && status < 300; }
  bool reachable() const { return status != 0; }
  bool isJson() const { return !json.isNull(); }
  QJsonObject object() const { return json.object(); }
  // "200 OK", "404", "offline: Connection refused", ...
  QString statusText() const;
};

class ApiClient : public QObject {
  Q_OBJECT
 public:
  using Callback = std::function<void(const ApiResult&)>;

  explicit ApiClient(QObject* parent = nullptr);

  void setBaseUrl(const QUrl& url);
  QUrl baseUrl() const { return base_; }
  void setTimeoutMs(int ms) { timeoutMs_ = ms; }
  int timeoutMs() const { return timeoutMs_; }

  void get(const QString& path, Callback cb = {}, bool quiet = false);
  void postJson(const QString& path, const QJsonDocument& body, Callback cb = {});
  void postBytes(const QString& path, const QByteArray& bytes, const QString& contentType,
                 const QString& summary, Callback cb = {});

  // Guess an image MIME type from its magic bytes (PNG / JPEG / BMP / ...).
  static QString sniffImageType(const QByteArray& bytes);

 Q_SIGNALS:
  void exchanged(const ApiResult& result);

 private:
  void send(const QString& method, const QString& path, const QByteArray& body,
            const QString& contentType, const QString& summary, Callback cb, bool quiet);

  QNetworkAccessManager nam_;
  QUrl base_{QStringLiteral("http://127.0.0.1:8080")};
  int timeoutMs_ = 4000;
};
