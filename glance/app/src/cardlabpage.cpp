#include <QComboBox>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QUrlQuery>
#include <QVBoxLayout>

#include <algorithm>

#include "pages.h"
#include "widgets.h"

namespace {

QLabel* metricCell(QGridLayout* g, int row, int col, const QString& name) {
  auto* box = new QVBoxLayout;
  box->setSpacing(2);
  box->addWidget(makeLabel(name.toUpper(), "section"));
  auto* v = makeLabel(QStringLiteral("—"), "metricSmall");
  v->setTextInteractionFlags(Qt::TextSelectableByMouse);
  box->addWidget(v);
  g->addLayout(box, row, col);
  return v;
}

Tone verificationTone(const QString& v) {
  if (v == QLatin1String("confirmed") || v == QLatin1String("not_required")) return Tone::Success;
  if (v == QLatin1String("changed") || v == QLatin1String("ocr_recovered")) return Tone::Info;
  if (v == QLatin1String("unverified")) return Tone::Warning;
  if (v == QLatin1String("empty")) return Tone::Neutral;
  return Tone::Danger;
}

QString suitName(const QString& s) {
  if (s.isEmpty()) return s;
  return s.left(1).toUpper() + s.mid(1);
}

QChar suitLetter(const QString& s) {
  const QString l = s.toLower();
  if (l.startsWith(QLatin1String("heart"))) return QLatin1Char('h');
  if (l.startsWith(QLatin1String("diamond"))) return QLatin1Char('d');
  if (l.startsWith(QLatin1String("club"))) return QLatin1Char('c');
  if (l.startsWith(QLatin1String("spade"))) return QLatin1Char('s');
  return l.size() == 1 ? l.at(0) : QChar();
}

}  // namespace

CardLabPage::CardLabPage(ApiClient* api, QWidget* parent) : QWidget(parent), api_(api) {
  auto* body = new QWidget;
  auto* root = new QVBoxLayout(body);
  root->setContentsMargins(28, 24, 28, 28);
  root->setSpacing(16);
  root->addWidget(makePageHeader(tr("Card lab"),
                                 tr("Recognize a single card crop with POST /recognize-card and see why.")));

  auto* row = new QHBoxLayout;
  row->setSpacing(16);

  // Left: input.
  QVBoxLayout* lv = nullptr;
  QFrame* left = makePanel(tr("Card crop"), &lv);
  drop_ = new DropZone(tr("Drop a card crop"));
  drop_->setMinimumHeight(260);
  lv->addWidget(drop_, 1);
  auto* sh = new QHBoxLayout;
  sh->addWidget(makeLabel(tr("Slot"), "muted"));
  slot_ = new QComboBox;
  slot_->setEditable(true);
  slot_->addItems({QString(), QStringLiteral("my1"), QStringLiteral("my2"), QStringLiteral("hero_card_1"),
                   QStringLiteral("hero_card_2"), QStringLiteral("board1"), QStringLiteral("board2"),
                   QStringLiteral("board3"), QStringLiteral("board4"), QStringLiteral("board5")});
  slot_->setToolTip(tr("Optional ?slot= — selects slot-specific suit regions in the calibration profile"));
  slot_->setMinimumWidth(140);
  slot_->lineEdit()->setPlaceholderText(tr("none"));
  sh->addWidget(slot_);
  sh->addStretch();
  run_ = new QPushButton(tr("Recognize"));
  run_->setProperty("kind", "primary");
  run_->setEnabled(false);
  sh->addWidget(run_);
  lv->addLayout(sh);
  banner_ = makeLabel(QString(), "banner");
  banner_->setWordWrap(true);
  banner_->hide();
  lv->addWidget(banner_);
  left->setMinimumWidth(340);
  row->addWidget(left, 2);

  // Right: reading.
  QVBoxLayout* rv = nullptr;
  QFrame* right = makePanel(tr("Reading"), &rv);
  auto* head = new QHBoxLayout;
  head->setSpacing(18);
  card_ = new CardWidget(QSize(96, 136));
  head->addWidget(card_, 0, Qt::AlignTop);
  auto* hv = new QVBoxLayout;
  hv->setSpacing(6);
  headline_ = makeLabel(tr("No reading yet"), "title");
  subline_ = makeLabel(tr("Pick a crop and press Recognize."), "muted");
  subline_->setWordWrap(true);
  hv->addWidget(headline_);
  hv->addWidget(subline_);
  auto* pills = new QHBoxLayout;
  pills->setSpacing(6);
  verification_ = new Pill(tr("verification"), Tone::Neutral);
  occupancy_ = new Pill(tr("occupancy"), Tone::Neutral);
  color_ = new Pill(tr("colour"), Tone::Neutral);
  pills->addWidget(verification_);
  pills->addWidget(occupancy_);
  pills->addWidget(color_);
  pills->addStretch();
  hv->addLayout(pills);
  hv->addStretch();
  head->addLayout(hv, 1);
  rv->addLayout(head);
  rv->addWidget(makeDivider());
  auto* g = new QGridLayout;
  g->setHorizontalSpacing(20);
  g->setVerticalSpacing(12);
  rank_ = metricCell(g, 0, 0, tr("Rank"));
  rankConf_ = metricCell(g, 0, 1, tr("Confidence"));
  rankMargin_ = metricCell(g, 0, 2, tr("Margin"));
  rankSrc_ = metricCell(g, 0, 3, tr("Source"));
  suit_ = metricCell(g, 1, 0, tr("Suit"));
  suitConf_ = metricCell(g, 1, 1, tr("Confidence"));
  suitMargin_ = metricCell(g, 1, 2, tr("Margin"));
  suitSrc_ = metricCell(g, 1, 3, tr("Source"));
  for (QLabel* l : {rankSrc_, suitSrc_}) {
    l->setProperty("role", "mono");
    l->setWordWrap(true);
  }
  for (int c = 0; c < 4; ++c) g->setColumnStretch(c, 1);
  rv->addLayout(g);
  rv->addStretch();
  row->addWidget(right, 3);
  root->addLayout(row);

  auto* row2 = new QHBoxLayout;
  row2->setSpacing(16);
  QVBoxLayout* sv = nullptr;
  QFrame* suits = makePanel(tr("Per-suit scores"), &sv);
  suitBox_ = new QWidget;
  suitBars_ = new QVBoxLayout(suitBox_);
  suitBars_->setContentsMargins(0, 0, 0, 0);
  suitBars_->setSpacing(6);
  for (const char* s : {"hearts", "diamonds", "clubs", "spades"}) {
    auto* b = new ScoreBar(suitName(QString::fromLatin1(s)));
    b->setValue(0, 1, QStringLiteral("—"));
    suitBars_->addWidget(b);
  }
  sv->addWidget(suitBox_);
  sv->addStretch();
  row2->addWidget(suits, 1);

  QVBoxLayout* ov = nullptr;
  QFrame* occ = makePanel(tr("Occupancy"), &ov);
  white_ = new ScoreBar(tr("White ratio"));
  green_ = new ScoreBar(tr("Green ratio"));
  edge_ = new ScoreBar(tr("Edge ratio"));
  bright_ = new ScoreBar(tr("Mean brightness"));
  bstd_ = new ScoreBar(tr("Brightness std-dev"));
  for (ScoreBar* b : {white_, green_, edge_, bright_, bstd_}) {
    b->setValue(0, 1, QStringLiteral("—"));
    ov->addWidget(b);
  }
  white_->setThreshold(0.55);
  occReason_ = makeLabel(QString(), "faint");
  occReason_->setWordWrap(true);
  ov->addWidget(occReason_);
  ov->addStretch();
  row2->addWidget(occ, 1);
  root->addLayout(row2);
  root->addStretch();

  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  lay->addWidget(scrollPage(body));

  connect(drop_, &DropZone::imageChanged, this, [this] { run_->setEnabled(drop_->hasImage()); });
  connect(run_, &QPushButton::clicked, this, &CardLabPage::recognize);
}

void CardLabPage::setCrop(const QByteArray& png, const QString& name) { drop_->setImageBytes(png, name); }

void CardLabPage::recognize() {
  if (!drop_->hasImage()) return;
  QString path = QStringLiteral("/recognize-card");
  const QString slot = slot_->currentText().trimmed();
  if (!slot.isEmpty()) {
    QUrlQuery q;
    q.addQueryItem(QStringLiteral("slot"), slot);
    path += QLatin1Char('?') + q.toString(QUrl::FullyEncoded);
  }
  const QByteArray bytes = drop_->bytes();
  const QString type = ApiClient::sniffImageType(bytes);
  run_->setEnabled(false);
  banner_->hide();
  api_->postBytes(path, bytes, type, QStringLiteral("%1, %2 (%3)").arg(drop_->fileName(), fmtBytes(bytes.size()), type),
                  [this](const ApiResult& r) {
                    run_->setEnabled(drop_->hasImage());
                    if (r.ok() && r.json.isObject()) {
                      applyReading(r.object());
                      return;
                    }
                    QString msg;
                    if (r.status == 409)
                      msg = tr("Card vision is not configured on this server (409). Start glance-server with card "
                               "vision templates to enable /recognize-card.");
                    else if (r.status == 404 && r.error.isEmpty())
                      msg = tr("This server has no POST /recognize-card route.");
                    else
                      msg = tr("%1 — %2").arg(r.statusText(), r.error.isEmpty() ? tr("request failed") : r.error);
                    banner_->setText(msg);
                    banner_->show();
                  });
}

void CardLabPage::applyReading(const QJsonObject& r) {
  banner_->hide();
  const bool ok = r.value(QStringLiteral("recognized")).toBool();
  const QString cardId = r.value(QStringLiteral("card")).toString();
  const QString rank = r.value(QStringLiteral("rank")).toString();
  const QString suit = r.value(QStringLiteral("suit")).toString();
  const bool skipped = r.value(QStringLiteral("skipped")).toBool();

  QString shown = cardId;
  if (shown.isEmpty() && !rank.isEmpty()) {
    const QChar sl = suitLetter(suit);
    shown = sl.isNull() ? QStringLiteral("?") : rank + sl;
  }
  if (shown.isEmpty()) shown = skipped ? QString() : QStringLiteral("?");
  card_->setCard(shown);

  QString rankName = rank == QLatin1String("T") ? QStringLiteral("10") : rank;
  if (ok)
    headline_->setText(tr("%1 of %2").arg(rankName, suitName(suit)));
  else if (skipped)
    headline_->setText(tr("Empty slot"));
  else
    headline_->setText(tr("Not recognized"));
  QStringList sub;
  if (ok) sub << tr("Card id %1").arg(cardId);
  if (r.contains(QStringLiteral("glyph_rank")))
    sub << tr("glyph read %1 before verification").arg(r.value(QStringLiteral("glyph_rank")).toString(tr("nothing")));
  if (skipped) sub << tr("recognition skipped: slot detected as empty");
  if (!ok && !skipped) sub << tr("rank %1, suit %2").arg(rank.isEmpty() ? tr("unread") : rank, suit.isEmpty() ? tr("unread") : suit);
  subline_->setText(sub.join(QStringLiteral("  ·  ")));

  QString ver = r.value(QStringLiteral("rank_verification")).toString();
  const Tone vt = verificationTone(ver);
  verification_->set(ver.isEmpty() ? tr("verification —") : ver.replace(QLatin1Char('_'), QLatin1Char(' ')), vt);
  const QJsonObject occ = r.value(QStringLiteral("occupancy")).toObject();
  const QString occState = occ.value(QStringLiteral("state")).toString();
  occupancy_->set(occState.isEmpty() ? tr("occupancy —") : occState,
                  occState == QLatin1String("occupied") ? Tone::Success
                  : occState == QLatin1String("empty")  ? Tone::Neutral
                                                        : Tone::Warning);
  const QString col = r.value(QStringLiteral("suit_color")).toString();
  color_->set(col.isEmpty() ? tr("colour —") : col,
              col == QLatin1String("red") ? Tone::Danger : col == QLatin1String("black") ? Tone::Accent : Tone::Neutral);

  auto pct = [&](const char* k) {
    const QJsonValue v = r.value(QLatin1String(k));
    return v.isDouble() ? fmtPercent(v.toDouble()) : QStringLiteral("—");
  };
  auto num = [&](const char* k) {
    const QJsonValue v = r.value(QLatin1String(k));
    return v.isDouble() ? QString::number(v.toDouble(), 'f', 3) : QStringLiteral("—");
  };
  auto str = [&](const char* k) {
    const QString s = r.value(QLatin1String(k)).toString();
    return s.isEmpty() ? QStringLiteral("—") : s;
  };
  rank_->setText(rankName.isEmpty() ? QStringLiteral("—") : rankName);
  rankConf_->setText(pct("rank_confidence"));
  rankMargin_->setText(num("rank_margin"));
  rankSrc_->setText(str("rank_source"));
  suit_->setText(suit.isEmpty() ? QStringLiteral("—") : suitName(suit));
  suitConf_->setText(pct("suit_confidence"));
  suitMargin_->setText(num("suit_margin"));
  suitSrc_->setText(str("suit_source"));

  // Per-suit bars: known suits first, then any extra labels, best highlighted.
  while (QLayoutItem* it = suitBars_->takeAt(0)) {
    delete it->widget();
    delete it;
  }
  const QJsonObject scores = r.value(QStringLiteral("suit_scores")).toObject();
  QStringList keys = {QStringLiteral("hearts"), QStringLiteral("diamonds"), QStringLiteral("clubs"),
                      QStringLiteral("spades")};
  for (const QString& k : scores.keys())
    if (!keys.contains(k)) keys << k;
  double best = -1;
  for (const QString& k : keys) best = std::max(best, scores.value(k).toDouble(-1));
  for (const QString& k : keys) {
    auto* b = new ScoreBar(suitName(k));
    const QJsonValue v = scores.value(k);
    if (v.isDouble()) {
      b->setValue(v.toDouble(), 1.0, QString::number(v.toDouble(), 'f', 3));
      b->setHighlight(v.toDouble() == best && (k == suit || suit.isEmpty()));
    } else {
      b->setValue(0, 1, QStringLiteral("—"));
    }
    b->setThreshold(0.75);
    suitBars_->addWidget(b);
  }

  auto occBar = [&](ScoreBar* b, const char* k, double max) {
    const QJsonValue v = occ.value(QLatin1String(k));
    if (v.isDouble())
      b->setValue(v.toDouble(), max, max == 1.0 ? fmtPercent(v.toDouble()) : QString::number(v.toDouble(), 'f', 1));
    else
      b->setValue(0, 1, QStringLiteral("—"));
  };
  occBar(white_, "white_ratio", 1.0);
  occBar(green_, "green_ratio", 1.0);
  occBar(edge_, "edge_ratio", 1.0);
  occBar(bright_, "mean_brightness", 255.0);
  occBar(bstd_, "brightness_std", 128.0);
  occReason_->setText(occ.value(QStringLiteral("reason")).toString());
}
