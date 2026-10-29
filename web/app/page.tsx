"use client";

import { useMemo, useRef, useState } from "react";

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

const PLACES = [
  { label: "یوسف‌آباد", latitude: 35.715298, longitude: 51.404343 },
  { label: "سعادت‌آباد", latitude: 35.780833, longitude: 51.371389 },
  { label: "تجریش", latitude: 35.804167, longitude: 51.428889 },
  { label: "تهرانپارس", latitude: 35.733333, longitude: 51.533333 },
];

type Step = "say" | "check" | "basket";
type HeardItem = { name: string; raw_text: string; title: string; quantity: number };

const STEP_MARK: Record<Step, string> = { say: "۱ از ۳", check: "۲ از ۳", basket: "۳ از ۳" };
const STEP_AT: Record<Step, number> = { say: 0, check: 1, basket: 2 };

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
  const [step, setStep] = useState<Step>("say");
  const [text, setText] = useState("");
  const [items, setItems] = useState<HeardItem[]>([]);
  const [placeIndex, setPlaceIndex] = useState(0);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [selected, setSelected] = useState("optimal");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [openKey, setOpenKey] = useState("");
  const [savedKey, setSavedKey] = useState("");
  const [recording, setRecording] = useState(false);
  const [hearing, setHearing] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const shelves = useMemo(() => (result ? buildShelves(result) : []), [result]);
  const shelf = shelves.find((item) => item.id === selected) ?? shelves[0];

  async function sendRecording(blob: Blob) {
    setHearing(true);
    setError("");
    try {
      const bytes = new Uint8Array(await blob.arrayBuffer());
      let binary = "";
      for (let index = 0; index < bytes.length; index += 0x2000) {
        binary += String.fromCharCode(...bytes.subarray(index, index + 0x2000));
      }
      const response = await fetch("/api/transcribe", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          audio_base64: btoa(binary),
          mime_type: blob.type || "audio/webm",
        }),
      });
      const payload = (await response.json()) as { text?: string; error?: string };
      if (!response.ok || !payload.text) {
        setError(payload.error || "صدا واضح نبود. دوباره ضبط کن یا لیست را بنویس.");
        return;
      }
      setText(payload.text);
      await review(payload.text);
    } catch {
      setError("ارتباط برای تبدیل صدا برقرار نشد.");
    } finally {
      setHearing(false);
    }
  }

  async function toggleRecord() {
    if (hearing) return;
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    setError("");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("اجازهٔ میکروفون داده نشد.");
      return;
    }
    const preferred = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
    const mimeType = preferred.find((item) => MediaRecorder.isTypeSupported(item));
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      setRecording(false);
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
      void sendRecording(blob);
    };
    recorderRef.current = recorder;
    recorder.start();
    setRecording(true);
  }

  async function review(list: string) {
    const trimmed = list.trim();
    if (!trimmed || pending) return;
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/parse", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
      });
      const payload = (await response.json()) as { items?: HeardItem[]; error?: string };
      if (!response.ok || !payload.items?.length) {
        setError(payload.error || "از این لیست قلمی درنیامد.");
        return;
      }
      setItems(payload.items);
      setStep("check");
    } catch {
      setError("ارتباط برای خواندن لیست برقرار نشد.");
    } finally {
      setPending(false);
    }
  }

  async function compare() {
    const list = items.map((item) => item.raw_text || item.title).filter(Boolean).join("، ");
    const place = PLACES[placeIndex];
    if (!list || !place || pending) return;
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/compare", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          text: list,
          latitude: place.latitude,
          longitude: place.longitude,
        }),
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
      setStep("basket");
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
        <span className="phase">{STEP_MARK[step]}</span>
      </header>
      <div className="steps" aria-hidden="true">
        {[0, 1, 2].map((mark) => (
          <span className={mark <= STEP_AT[step] ? "on" : undefined} key={mark} />
        ))}
      </div>
      <p className="sr">
        {step === "say"
          ? "مرحله ۱ از ۳. گفتن یا نوشتن لیست."
          : step === "check"
            ? "مرحله ۲ از ۳. تأیید قلم‌ها و محل تحویل."
            : "مرحله ۳ از ۳. سبد و قیمت."}
      </p>

      {step === "say" ? (
        <section className="screen ask">
          <h1>لیستت را بگو</h1>
          <p className="muted">یا اگر راحت‌تری، بنویس.</p>
          <div className="mic-wrap">
            <button
              className={recording ? "mic live" : "mic"}
              type="button"
              onClick={toggleRecord}
              disabled={hearing || pending}
              aria-label={recording ? "پایان ضبط" : "ضبط لیست خرید"}
            >
              {hearing ? "…" : recording ? "پایان" : "ضبط"}
            </button>
          </div>
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
            <button className="primary" type="button" onClick={() => review(text)} disabled={pending || hearing || !text.trim()}>
              {pending ? "داریم می‌خوانیم…" : "ادامه"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "check" ? (
        <section className="screen">
          <h1>این‌ها را برداشتیم</h1>
          <p className="muted">غلط‌ها را حذف کن و محل تحویل را انتخاب کن.</p>
          <div className="sheet">
            {items.map((item, index) => (
              <article className="row" key={`${item.raw_text}-${index}`}>
                <div className="row-head">
                  <h2>{item.title}</h2>
                  <button
                    className="quiet"
                    type="button"
                    onClick={() => setItems(items.filter((_, itemIndex) => itemIndex !== index))}
                  >
                    حذف
                  </button>
                </div>
              </article>
            ))}
          </div>
          <div className="chips">
            {PLACES.map((place, index) => (
              <button
                className={placeIndex === index ? "chip on" : "chip"}
                type="button"
                key={place.label}
                onClick={() => setPlaceIndex(index)}
              >
                {place.label}
              </button>
            ))}
          </div>
          <div className="dock">
            {error ? <p className="alert">{error}</p> : null}
            <button className="quiet" type="button" onClick={() => { setStep("say"); setError(""); }}>
              لیست را عوض کن
            </button>
            <button className="primary" type="button" onClick={compare} disabled={pending || items.length === 0}>
              {pending ? "در حال مقایسه…" : "مقایسه کن"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "basket" ? (
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
                setStep("check");
                setError("");
              }}
            >
              اصلاح لیست
            </button>
          </div>
        </section>
      ) : null}
    </main>
  );
}
