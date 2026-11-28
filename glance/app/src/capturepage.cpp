#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QPushButton>
#include <QVBoxLayout>

#include "pages.h"
#include "widgets.h"

CapturePage::CapturePage(ApiClient* api, QWidget* parent) : QWidget(parent), api_(api) {
  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(28, 24, 28, 24);
  root->setSpacing(16);
  root->addWidget(makePageHeader(
      tr("Capture"), tr("Send a screenshot to POST /capture and inspect the frame the server parsed.")));

  auto* row = new QHBoxLayout;
  row->setSpacing(16);

  QVBoxLayout* lv = nullptr;
  QFrame* left = makePanel(tr("Screenshot"), &lv);
  drop_ = new DropZone(tr("Drop a table screenshot"));
  lv->addWidget(drop_, 1);
  auto* bh = new QHBoxLayout;
  auto* browse = new QPushButton(tr("Choose file…"));
  auto* clear = new QPushButton(tr("Clear"));
  clear->setProperty("kind", "ghost");
  sendBtn_ = new QPushButton(tr("Send to /capture"));
  sendBtn_->setProperty("kind", "primary");
  sendBtn_->setEnabled(false);
  bh->addWidget(browse);
  bh->addWidget(clear);
  bh->addStretch();
  bh->addWidget(sendBtn_);
  lv->addLayout(bh);
  lv->addWidget(makeDivider());
  auto* rh = new QHBoxLayout;
  result_ = new Pill(tr("Not sent"), Tone::Neutral);
  rh->addWidget(result_);
  resultText_ = makeLabel(tr("The parsed state also feeds the Live table page."), "muted");
  resultText_->setWordWrap(true);
  rh->addWidget(resultText_, 1);
  lv->addLayout(rh);
  row->addWidget(left, 1);

  QVBoxLayout* rv = nullptr;
  QFrame* right = makePanel(tr("Server frame  ·  GET /frame.png"), &rv);
  frame_ = new ImageView(tr("No frame loaded"));
  rv->addWidget(frame_, 1);
  auto* fh = new QHBoxLayout;
  frameStatus_ = new Pill(tr("—"), Tone::Neutral);
  fh->addWidget(frameStatus_);
  frameCaption_ = makeLabel(tr("Click the frame to pick a point for the Control page."), "faint");
  frameCaption_->setWordWrap(true);
  fh->addWidget(frameCaption_, 1);
  auto* refresh = new QPushButton(tr("Refresh frame"));
  fh->addWidget(refresh);
  rv->addLayout(fh);
  row->addWidget(right, 1);
  root->addLayout(row, 1);

  connect(browse, &QPushButton::clicked, drop_, &DropZone::browse);
  connect(clear, &QPushButton::clicked, drop_, &DropZone::clear);
  connect(drop_, &DropZone::imageChanged, this, [this] { sendBtn_->setEnabled(drop_->hasImage()); });
  connect(sendBtn_, &QPushButton::clicked, this, &CapturePage::send);
  connect(refresh, &QPushButton::clicked, this, &CapturePage::refreshFrame);
  connect(frame_, &ImageView::pointPicked, this, [this](QPoint p) {
    frameCaption_->setText(tr("Picked %1, %2 → sent to Control as a raw click point.").arg(p.x()).arg(p.y()));
    Q_EMIT pointPicked(p);
  });
}

void CapturePage::setCaptureResult(Tone tone, const QString& pill, const QString& text) {
  result_->set(pill, tone);
  resultText_->setText(text);
}

void CapturePage::setFrameImage(const QImage& img, const QString& caption) {
  frame_->setImage(img);
  frameStatus_->set(QStringLiteral("%1 × %2").arg(img.width()).arg(img.height()), Tone::Accent);
  if (!caption.isEmpty()) frameCaption_->setText(caption);
}

void CapturePage::setScreenshot(const QByteArray& bytes, const QString& name) { drop_->setImageBytes(bytes, name); }

void CapturePage::send() {
  if (!drop_->hasImage()) return;
  const QByteArray bytes = drop_->bytes();
  const QString type = ApiClient::sniffImageType(bytes);
  sendBtn_->setEnabled(false);
  result_->set(tr("Sending…"), Tone::Accent);
  api_->postBytes(QStringLiteral("/capture"), bytes, type,
                  QStringLiteral("%1, %2 (%3)").arg(drop_->fileName(), fmtBytes(bytes.size()), type),
                  [this](const ApiResult& r) {
                    sendBtn_->setEnabled(drop_->hasImage());
                    if (r.ok() && r.json.isObject()) {
                      const QJsonObject s = r.object();
                      const int board = s.value(QStringLiteral("board")).toArray().size();
                      const QString stage = s.value(QStringLiteral("stage")).toString(tr("no stage"));
                      const QJsonObject v = s.value(QStringLiteral("validation")).toObject();
                      const int ne = v.value(QStringLiteral("error_count")).toInt();
                      setCaptureResult(ne ? Tone::Warning : Tone::Success, tr("Table found · %1 ms").arg(r.elapsedMs),
                                       tr("%1, %2 board card(s)%3").arg(stage).arg(board)
                                           .arg(ne ? tr(", %1 validation error(s)").arg(ne) : QString()));
                      Q_EMIT stateReceived(s);
                      if (cfg::get(cfg::kAutoFrame).toBool()) refreshFrame();
                    } else if (r.status == 422) {
                      setCaptureResult(Tone::Warning, tr("422 · no table"),
                                       r.error.isEmpty() ? tr("Image decoded but the anchor was not found.") : r.error);
                      if (cfg::get(cfg::kAutoFrame).toBool()) refreshFrame();
                    } else {
                      setCaptureResult(Tone::Danger, r.reachable() ? r.statusText() : tr("Offline"),
                                       r.error.isEmpty() ? tr("Request failed.") : r.error);
                    }
                  });
}

void CapturePage::refreshFrame() {
  frameStatus_->set(tr("Loading…"), Tone::Accent);
  api_->get(QStringLiteral("/frame.png"), [this](const ApiResult& r) {
    if (r.ok()) {
      const QImage img = QImage::fromData(r.body);
      if (!img.isNull()) {
        setFrameImage(img, tr("Last frame the server decoded. Click it to pick a point for Control."));
        return;
      }
      frameStatus_->set(tr("Not an image"), Tone::Danger);
      return;
    }
    if (r.status == 404) {
      const bool noRoute = r.error.isEmpty();
      frameStatus_->set(noRoute ? tr("No route") : tr("No frame yet"), Tone::Warning);
      frame_->setPlaceholder(noRoute ? tr("This server has no GET /frame.png route") : r.error);
      frame_->setImage(QImage());
    } else {
      frameStatus_->set(r.reachable() ? r.statusText() : tr("Offline"), Tone::Danger);
    }
  });
}
