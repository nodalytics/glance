#include "apiclient.h"

#include <QElapsedTimer>
#include <QJsonParseError>
#include <QNetworkReply>
#include <QNetworkRequest>

QString ApiResult::statusText() const {
  if (status == 0) return error.isEmpty() ? QStringLiteral("no response") : error;
  QString s = QString::number(status);
  switch (status) {
    case 200: s += QStringLiteral(" OK"); break;
    case 400: s += QStringLiteral(" Bad Request"); break;
    case 404: s += QStringLiteral(" Not Found"); break;
    case 409: s += QStringLiteral(" Conflict"); break;
    case 422: s += QStringLiteral(" Unprocessable"); break;
    case 500: s += QStringLiteral(" Server Error"); break;
    default: break;
  }
  return s;
}

ApiClient::ApiClient(QObject* parent) : QObject(parent) {}

void ApiClient::setBaseUrl(const QUrl& url) {
  QUrl u = url;
  if (u.scheme().isEmpty()) u = QUrl(QStringLiteral("http://") + url.toString());
  // Base paths ("http://host:8080/glance") are kept; requests append to them.
  QString p = u.path();
  while (p.endsWith(QLatin1Char('/'))) p.chop(1);
  u.setPath(p);
  base_ = u;
}

QString ApiClient::sniffImageType(const QByteArray& b) {
  if (b.startsWith("\x89PNG")) return QStringLiteral("image/png");
  if (b.startsWith("\xFF\xD8")) return QStringLiteral("image/jpeg");
  if (b.startsWith("BM")) return QStringLiteral("image/bmp");
  if (b.startsWith("GIF8")) return QStringLiteral("image/gif");
  if (b.size() > 12 && b.mid(8, 4) == "WEBP") return QStringLiteral("image/webp");
  return QStringLiteral("application/octet-stream");
}

void ApiClient::get(const QString& path, Callback cb, bool quiet) {
  send(QStringLiteral("GET"), path, {}, {}, {}, std::move(cb), quiet);
}

void ApiClient::postJson(const QString& path, const QJsonDocument& body, Callback cb) {
  const QByteArray bytes = body.toJson(QJsonDocument::Compact);
  send(QStringLiteral("POST"), path, bytes, QStringLiteral("application/json"),
       QString::fromUtf8(bytes), std::move(cb), false);
}

void ApiClient::postBytes(const QString& path, const QByteArray& bytes,
                          const QString& contentType, const QString& summary, Callback cb) {
  send(QStringLiteral("POST"), path, bytes, contentType, summary, std::move(cb), false);
}

void ApiClient::send(const QString& method, const QString& path, const QByteArray& body,
                     const QString& contentType, const QString& summary, Callback cb,
                     bool quiet) {
  // Split "?query" off so QUrl does not percent-encode it into the path.
  QUrl url = base_;
  const qsizetype q = path.indexOf(QLatin1Char('?'));
  url.setPath(base_.path() + (q < 0 ? path : path.left(q)));
  if (q >= 0) url.setQuery(path.mid(q + 1));

  QNetworkRequest req(url);
  req.setTransferTimeout(timeoutMs_);
  req.setRawHeader("Accept", "application/json, image/png, */*");
  if (!contentType.isEmpty()) req.setHeader(QNetworkRequest::ContentTypeHeader, contentType);

  QElapsedTimer timer;
  timer.start();
  QNetworkReply* reply =
      method == QLatin1String("GET") ? nam_.get(req) : nam_.post(req, body);

  ApiResult base;
  base.method = method;
  base.path = path;
  base.url = url;
  base.quiet = quiet;
  base.requestSummary = summary;
  if (contentType == QLatin1String("application/json")) base.requestBody = body;

  connect(reply, &QNetworkReply::finished, this,
          [this, reply, timer, base, cb = std::move(cb)]() mutable {
            ApiResult r = base;
            r.elapsedMs = timer.elapsed();
            r.when = QDateTime::currentDateTime();
            r.status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
            r.body = reply->readAll();
            r.contentType = reply->header(QNetworkRequest::ContentTypeHeader).toString();
            if (r.status == 0) {
              r.error = reply->error() == QNetworkReply::OperationCanceledError
                            ? QStringLiteral("timed out")
                            : reply->errorString();
            }
            const QByteArray trimmed = r.body.trimmed();
            if (r.contentType.contains(QLatin1String("json")) || trimmed.startsWith('{') ||
                trimmed.startsWith('[')) {
              QJsonParseError pe;
              QJsonDocument doc = QJsonDocument::fromJson(r.body, &pe);
              if (pe.error == QJsonParseError::NoError) r.json = doc;
            }
            if (r.status != 0 && !r.ok() && r.json.isObject()) {
              r.error = r.json.object().value(QStringLiteral("error")).toString();
            }
            reply->deleteLater();
            if (cb) cb(r);
            Q_EMIT exchanged(r);
          });
}
