#include <QDateTime>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLabel>
#include <QPushButton>
#include <QSpinBox>
#include <QTimer>
#include <QVBoxLayout>

#include "pages.h"
#include "tableview.h"
#include "widgets.h"

namespace {

QLabel* addRow(QGridLayout* g, int row, const QString& name) {
  g->addWidget(makeLabel(name, "muted"), row, 0);
  auto* v = makeLabel(QStringLiteral("—"), "metricSmall");
  v->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
  v->setTextInteractionFlags(Qt::TextSelectableByMouse);
  g->addWidget(v, row, 1);
  return v;
}

}  // namespace

TablePage::TablePage(ApiClient* api, QWidget* parent) : QWidget(parent), api_(api) {
  timer_ = new QTimer(this);
  connect(timer_, &QTimer::timeout, this, &TablePage::refresh);

  auto* root = new QVBoxLayout(this);
  root->setContentsMargins(28, 24, 28, 24);
  root->setSpacing(16);

  // Toolbar: live toggle, interval, manual refresh.
  auto* tools = new QWidget;
  auto* th = new QHBoxLayout(tools);
  th->setContentsMargins(0, 0, 0, 0);
  th->setSpacing(8);
  status_ = new Pill(tr("Idle"), Tone::Neutral);
  updated_ = makeLabel(QString(), "faint");
  live_ = new QPushButton(tr("Live"));
  live_->setCheckable(true);
  live_->setProperty("kind", "toggle");
  live_->setChecked(cfg::get(cfg::kStateLive).toBool());
  live_->setToolTip(tr("Poll GET /state continuously"));
  interval_ = new QSpinBox;
  interval_->setRange(100, 60000);
  interval_->setSingleStep(100);
  interval_->setSuffix(tr(" ms"));
  interval_->setValue(cfg::get(cfg::kStateMs).toInt());
  interval_->setToolTip(tr("Polling interval"));
  auto* refresh = new QPushButton(tr("Refresh"));
  th->addWidget(updated_);
  th->addSpacing(8);
  th->addWidget(status_);
  th->addSpacing(8);
  th->addWidget(live_);
  th->addWidget(interval_);
  th->addWidget(refresh);
  root->addWidget(makePageHeader(tr("Live table"), tr("GET /state rendered as a table, with the server's own validation."), tools));

  connect(live_, &QPushButton::toggled, this, [this](bool on) {
    cfg::set(cfg::kStateLive, on);
    updateTimer();
  });
  connect(interval_, &QSpinBox::valueChanged, this, [this](int ms) {
    cfg::set(cfg::kStateMs, ms);
    timer_->setInterval(ms);
  });
  connect(refresh, &QPushButton::clicked, this, &TablePage::refresh);

  auto* row = new QHBoxLayout;
  row->setSpacing(16);
  QVBoxLayout* tv = nullptr;
  QFrame* tablePanel = makePanel(QString(), &tv);
  tv->setContentsMargins(8, 8, 8, 8);
  table_ = new TableView;
  tv->addWidget(table_);
  row->addWidget(tablePanel, 1);

  auto* side = new QVBoxLayout;
  side->setSpacing(16);
  QVBoxLayout* hv = nullptr;
  QFrame* hand = makePanel(tr("Hand"), &hv);
  auto* g = new QGridLayout;
  g->setVerticalSpacing(10);
  g->setHorizontalSpacing(16);
  stage_ = addRow(g, 0, tr("Stage"));
  pot_ = addRow(g, 1, tr("Pot"));
  call_ = addRow(g, 2, tr("To call"));
  raise_ = addRow(g, 3, tr("Raise"));
  dealer_ = addRow(g, 4, tr("Dealer"));
  hero_ = addRow(g, 5, tr("Hero cards"));
  board_ = addRow(g, 6, tr("Board"));
  g->addWidget(makeLabel(tr("My turn"), "muted"), 7, 0);
  turn_ = new Pill(tr("—"), Tone::Neutral);
  g->addWidget(turn_, 7, 1, Qt::AlignRight);
  hv->addLayout(g);
  side->addWidget(hand);

  QVBoxLayout* vv = nullptr;
  QFrame* val = makePanel(tr("Validation"), &vv);
  valid_ = new Pill(tr("No state"), Tone::Neutral);
  vv->addWidget(valid_);
  issuesBox_ = new QWidget;
  issues_ = new QVBoxLayout(issuesBox_);
  issues_->setContentsMargins(0, 0, 0, 0);
  issues_->setSpacing(8);
  vv->addWidget(issuesBox_);
  vv->addStretch();
  side->addWidget(val, 1);

  auto* sideW = new QWidget;
  sideW->setLayout(side);
  sideW->setFixedWidth(300);
  row->addWidget(sideW);
  root->addLayout(row, 1);
  timer_->setInterval(interval_->value());
}

void TablePage::applyIntervalFromSettings() {
  interval_->setValue(cfg::get(cfg::kStateMs).toInt());
}

void TablePage::setConnected(bool on) {
  connected_ = on;
  updateTimer();
  if (on) refresh();
}

void TablePage::updateTimer() {
  if (connected_ && live_->isChecked()) {
    timer_->start();
  } else {
    timer_->stop();
    if (!connected_) status_->set(tr("Offline"), Tone::Neutral);
    else status_->set(tr("Paused"), Tone::Neutral);
  }
}

void TablePage::refresh() {
  if (inFlight_) return;  // never stack polls on a slow server
  inFlight_ = true;
  api_->get(QStringLiteral("/state"), [this](const ApiResult& r) {
    inFlight_ = false;
    onResult(r);
  }, true);
}

void TablePage::onResult(const ApiResult& r) {
  if (r.ok() && r.json.isObject()) {
    applyState(r.object());
    status_->set(live_->isChecked() && timer_->isActive() ? tr("Live · %1 ms").arg(r.elapsedMs) : tr("Updated"),
                 Tone::Success);
    return;
  }
  if (r.status == 404) {
    status_->set(tr("No state yet"), Tone::Warning);
    table_->clearState(tr("No table state yet"),
                       r.error.isEmpty() ? tr("POST a screenshot to /capture first") : r.error);
  } else {
    status_->set(r.reachable() ? r.statusText() : tr("Offline"), Tone::Danger);
  }
}

void TablePage::setRow(QLabel* l, const QString& v) { l->setText(v.isEmpty() ? QStringLiteral("—") : v); }

void TablePage::applyState(const QJsonObject& s) {
  table_->setState(s);
  if (!timer_->isActive()) status_->set(tr("Snapshot"), Tone::Accent);
  updated_->setText(tr("Updated %1").arg(QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss"))));
  setRow(stage_, s.value(QStringLiteral("stage")).toString());
  pot_->setText(fmtAmount(s.value(QStringLiteral("pot"))));
  call_->setText(fmtAmount(s.value(QStringLiteral("call"))));
  raise_->setText(fmtAmount(s.value(QStringLiteral("raise"))));
  const int d = s.value(QStringLiteral("dealer")).toInt(0);
  dealer_->setText(d ? tr("Seat %1").arg(d) : QStringLiteral("—"));
  auto cards = [](const QJsonValue& v) {
    QStringList out;
    for (const auto& e : v.toArray()) out << e.toString();
    return out.join(QLatin1Char(' '));
  };
  setRow(hero_, cards(s.value(QStringLiteral("my_cards"))));
  setRow(board_, cards(s.value(QStringLiteral("board"))));
  const bool turn = s.value(QStringLiteral("my_turn")).toBool();
  turn_->set(turn ? tr("Act now") : tr("Waiting"), turn ? Tone::Accent : Tone::Neutral);

  const QJsonObject v = s.value(QStringLiteral("validation")).toObject();
  const QByteArray key = QJsonDocument(v).toJson(QJsonDocument::Compact);
  if (key == lastValidation_) return;
  lastValidation_ = key;
  while (QLayoutItem* it = issues_->takeAt(0)) {
    delete it->widget();
    delete it;
  }
  if (v.isEmpty()) {
    valid_->set(tr("Not reported"), Tone::Neutral);
    return;
  }
  const int ne = v.value(QStringLiteral("error_count")).toInt();
  const int nw = v.value(QStringLiteral("warning_count")).toInt();
  if (v.value(QStringLiteral("valid")).toBool(ne == 0))
    valid_->set(nw ? tr("Valid · %1 warning(s)").arg(nw) : tr("Valid state"), nw ? Tone::Warning : Tone::Success);
  else
    valid_->set(tr("%1 error(s) · %2 warning(s)").arg(ne).arg(nw), Tone::Danger);

  auto addIssues = [this](const QJsonArray& arr, Tone tone) {
    for (const auto& e : arr) {
      const QJsonObject o = e.toObject();
      auto* w = new QFrame;
      w->setProperty("card", true);
      auto* l = new QVBoxLayout(w);
      l->setContentsMargins(12, 10, 12, 10);
      l->setSpacing(4);
      auto* top = new QHBoxLayout;
      top->addWidget(new Pill(o.value(QStringLiteral("code")).toString(), tone));
      top->addStretch();
      l->addLayout(top);
      auto* msg = makeLabel(o.value(QStringLiteral("message")).toString());
      msg->setWordWrap(true);
      l->addWidget(msg);
      QStringList slots;
      for (const auto& sl : o.value(QStringLiteral("slots")).toArray()) slots << sl.toString();
      if (!slots.isEmpty()) l->addWidget(makeLabel(tr("slots: %1").arg(slots.join(QStringLiteral(", "))), "faint"));
      issues_->addWidget(w);
    }
  };
  addIssues(v.value(QStringLiteral("errors")).toArray(), Tone::Danger);
  addIssues(v.value(QStringLiteral("warnings")).toArray(), Tone::Warning);
  if (ne == 0 && nw == 0) issues_->addWidget(makeLabel(tr("No impossible recognitions in this state."), "faint"));
}
