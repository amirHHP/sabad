"use client";

import { useMemo, useState } from "react";

type UnitOption = {
  product_id: string;
  title: string;
  text: string;
  is_cheapest: boolean;
};

type Line = {
  requested: string;
  title: string | null;
  product_id: string | null;
  platform: string;
  pack_price: number | null;
  unit_price_text: string | null;
  unit_options: UnitOption[];
  price_label: string | null;
  in_stock: boolean;
  explanation: string | null;
};

type OptimalLine = {
  platform: string;
  title: string;
  product_id?: string;
  pack_price: number | null;
  unit_price_text: string | null;
  quantity?: number;
  line_total?: number;
  price_label: string | null;
};

type StoreResult = {
  platform: string;
  title: string;
  lines: Line[];
};

type CompareResponse = {
  error?: string;
  optimal_total?: number;
  optimal_lines?: OptimalLine[];
  stores?: StoreResult[];
};

type FeedbackTarget = {
  requested: string;
  title: string;
  platform: string;
};

type Row = {
  key: string;
  title: string;
  price: number | null;
  inStock: boolean;
  detail: string | null;
  extra: string | null;
  feedback: FeedbackTarget | null;
};

type Shelf = {
  id: string;
  title: string;
  missing: number;
  rows: Row[];
  total: number | null;
  totalLabel: string;
};

const REASONS = ["حجم نامناسب", "نوع اشتباه", "محصول خودرو", "محصول ورزشی"];

const EXAMPLES = [
  { label: "شیر و نان", text: "شیر، نان، تخم‌مرغ" },
  { label: "شوینده", text: "شامپو، مایع ظرفشویی" },
  { label: "صبحانه", text: "پنیر، کره، چای" },
];

function toman(value: number | null) {
  if (value == null) return "";
  return `${Math.round(value).toLocaleString("en-US")} تومان`;
}

function cheaperSize(line: Line) {
  const options = line.unit_options ?? [];
  const cheapest = options.find((option) => option.is_cheapest);
  if (!cheapest || options.length < 2 || cheapest.product_id === line.product_id) {
    return null;
  }
  return `حجم دیگر ارزان‌تر است: ${cheapest.text}`;
}

function storeRows(store: StoreResult): Row[] {
  return store.lines.map((line) => {
    const extra = line.in_stock
      ? [line.price_label, cheaperSize(line)].filter(Boolean).join(" · ")
      : "";
    return {
      key: `${store.platform}-${line.requested}`,
      title: line.title || line.requested,
      price: line.pack_price,
      inStock: line.in_stock,
      detail: line.in_stock ? line.unit_price_text : line.explanation,
      extra: extra || null,
      feedback: line.title
        ? { requested: line.requested, title: line.title, platform: line.platform }
        : null,
    };
  });
}

function buildShelves(result: CompareResponse): Shelf[] {
  const shelves: Shelf[] = [];
  const optimal = result.optimal_lines ?? [];
  if (optimal.length > 0) {
    shelves.push({
      id: "optimal",
      title: "پیشنهادی",
      missing: 0,
      total: result.optimal_total ?? null,
      totalLabel: "جمع سبد",
      rows: optimal.map((line, index) => ({
        key: `opt-${line.platform}-${line.product_id ?? index}`,
        title: line.quantity && line.quantity > 1 ? `${line.title} · ${line.quantity} عدد` : line.title,
        price: line.line_total ?? line.pack_price,
        inStock: true,
        detail: line.unit_price_text,
        extra: line.price_label,
        feedback: { requested: line.title, title: line.title, platform: line.platform },
      })),
    });
  }
  for (const store of result.stores ?? []) {
    const rows = storeRows(store);
    const missing = rows.filter((row) => !row.inStock).length;
    const priced = rows.filter((row) => row.inStock && row.price != null);
    shelves.push({
      id: store.platform,
      title: store.title,
      missing,
      rows,
      total: priced.length ? priced.reduce((sum, row) => sum + (row.price ?? 0), 0) : null,
      totalLabel: missing ? "جمع موجودها" : "جمع این فروشگاه",
    });
  }
  return shelves;
}

export default function HomePage() {
  const [step, setStep] = useState<"ask" | "result">("ask");
  const [text, setText] = useState("");
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [selected, setSelected] = useState("optimal");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [openKey, setOpenKey] = useState("");
  const [savedKey, setSavedKey] = useState("");

  const shelves = useMemo(() => (result ? buildShelves(result) : []), [result]);
  const shelf = shelves.find((item) => item.id === selected) ?? shelves[0];

  async function compare() {
    const list = text.trim();
    if (!list || pending) return;
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/compare", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: list }),
      });
      const payload = (await response.json()) as CompareResponse;
      if (!response.ok) {
        setError(payload.error || "مقایسه انجام نشد.");
        return;
      }
      const next = buildShelves(payload);
      setResult(payload);
      setSelected(next[0]?.id ?? "optimal");
      setOpenKey("");
      setSavedKey("");
      setStep("result");
    } catch {
      setError("ارتباط با سرویس مقایسه برقرار نشد.");
    } finally {
      setPending(false);
    }
  }

  async function sendFeedback(row: Row, reason: string) {
    if (!row.feedback) return;
    setError("");
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ reason, ...row.feedback }),
    });
    if (response.ok) {
      setSavedKey(row.key);
      setOpenKey("");
    } else {
      setError("ثبت دلیل انجام نشد.");
    }
  }

  return (
    <main className="app">
      <header className="top">
        <span className="brand">سبد</span>
        <span className="phase">{step === "ask" ? "۱ از ۲" : "۲ از ۲"}</span>
      </header>
      <div className="steps" aria-hidden="true">
        <span className="on" />
        <span className={step === "result" ? "on" : undefined} />
      </div>
      <p className="sr">{step === "ask" ? "مرحله ۱ از ۲. نوشتن لیست." : "مرحله ۲ از ۲. نتیجهٔ مقایسه."}</p>

      {step === "ask" ? (
        <section className="screen ask">
          <h1>لیستت را بنویس</h1>
          <p className="muted">هر قلم را با ویرگول جدا کن.</p>
          <textarea
            value={text}
            placeholder="مثلاً شامپو، حوله، واکس"
            aria-label="لیست خرید"
            onChange={(event) => setText(event.target.value)}
          />
          <div className="chips">
            {EXAMPLES.map((example) => (
              <button
                className={text === example.text ? "chip on" : "chip"}
                type="button"
                key={example.label}
                onClick={() => setText(example.text)}
              >
                {example.label}
              </button>
            ))}
          </div>
          <div className="dock">
            {error ? <p className="alert">{error}</p> : null}
            <button className="primary" type="button" onClick={compare} disabled={pending || !text.trim()}>
              {pending ? "در حال مقایسه…" : "مقایسه کن"}
            </button>
          </div>
        </section>
      ) : (
        <section className="screen">
          {shelf ? (
            <>
              <p className="total-label">{shelf.totalLabel}</p>
              <p className="total">{shelf.total == null ? "قیمتی نیست" : toman(shelf.total)}</p>
              {shelf.missing > 0 ? (
                <p className="gap-note">{shelf.missing} قلم در این فروشگاه نیست</p>
              ) : null}
              <div className="tabs" role="tablist" aria-label="فروشگاه‌ها">
                {shelves.map((item) => (
                  <button
                    className="tab"
                    type="button"
                    role="tab"
                    key={item.id}
                    aria-selected={item.id === shelf.id}
                    onClick={() => {
                      setSelected(item.id);
                      setOpenKey("");
                    }}
                  >
                    {item.title}
                    {item.missing > 0 ? <span className="dot" /> : null}
                  </button>
                ))}
              </div>
              <div className="sheet" role="tabpanel">
                {shelf.rows.length === 0 ? <p className="empty">برای این لیست چیزی پیدا نشد.</p> : null}
                {shelf.rows.map((row) => (
                  <article className="row" key={row.key}>
                    <div className="row-head">
                      <h2>{row.title}</h2>
                      <span className={row.inStock ? "price" : "price missing"}>
                        {row.inStock ? toman(row.price) : "نیست"}
                      </span>
                    </div>
                    {row.detail ? <p className="detail">{row.detail}</p> : null}
                    {row.extra ? <p className="extra">{row.extra}</p> : null}
                    {row.feedback && savedKey === row.key ? <p className="saved">ثبت شد.</p> : null}
                    {row.feedback && savedKey !== row.key ? (
                      <>
                        <button
                          className="quiet"
                          type="button"
                          onClick={() => setOpenKey(openKey === row.key ? "" : row.key)}
                        >
                          مناسب نیست
                        </button>
                        {openKey === row.key ? (
                          <div className="reasons">
                            {REASONS.map((reason) => (
                              <button
                                className="reason"
                                type="button"
                                key={reason}
                                onClick={() => sendFeedback(row, reason)}
                              >
                                {reason}
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </article>
                ))}
              </div>
            </>
          ) : (
            <p className="empty">برای این لیست چیزی پیدا نشد.</p>
          )}
          {error ? <p className="alert">{error}</p> : null}
          <div className="dock">
            <button
              className="secondary"
              type="button"
              onClick={() => {
                setStep("ask");
                setError("");
              }}
            >
              ویرایش لیست
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
