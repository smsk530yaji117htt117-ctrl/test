import { useState, useMemo, useCallback } from "react";

// ─── Data ───────────────────────────────────────────────────────────────────

const TYPES = {
  S: {
    key: "S",
    name: "設計者",
    en: "Strategic Architect",
    axes: ["論理", "構想"],
    color: "#8B5CF6",
    colorLight: "#F5F3FF",
    char: "🎯",
    tagline: "見通す力の持ち主",
    prompt:
      "私は「設計者タイプ」です。全体の構造を見渡して筋道を立てるのが得意で、論理的かつ構想的に物事を考えます。会話では、まず全体像や目的を確認し、構造的に整理してから、具体策を提案してください。抽象的な問いにもしっかり付き合ってくれると助かります。",
    bestMatch: "C",
    code: "SA",
    reading: {
      intro:
        "あなたは、物事の「全体像」が見えないと動けないタイプ。友達の相談にも「そもそもさ…」って本質を突くアドバイスをして驚かれること、ない？",
      aruaru: [
        "計画を立てるのが好きだけど、計画通りにいかないと地味にイライラする",
        "「で、結局なにが言いたいの？」と思いがち（口には出さないけど）",
        "グループワークで自然とまとめ役になってるけど、本当はひとりで考えたい",
        "寝る前に「あの問題、こうすれば解決するんじゃ…」と急にひらめく",
        "人の話を聞きながら、頭の中で構造化してる自分に気づく",
      ],
      love: "好きな人ができると、相手の行動パターンを無意識に分析し始める。告白のタイミングすら「最適解」を考えてしまって、結局逃すことも。でも一度付き合うと、相手の人生設計まで一緒に考えてくれる、めちゃくちゃ頼れるパートナーになる。",
      school:
        "テスト勉強は「全体の出題傾向」を把握してから始めるタイプ。先にノートのまとめ方を設計して、実際の勉強時間が足りなくなりがち。でもそのフレームワークが完成したときの快感は何物にも代えがたい。",
      stress:
        "ストレスが溜まると「全部自分で設計し直したい」衝動に駆られる。人に任せるのが怖くなって、気づいたら全部抱え込んでパンクするパターン。たまには「まあいっか」って手放すことも大事。",
      hidden:
        "実はめちゃくちゃ妄想家。頭の中で「もし自分が社長だったら」「もし世界を変えられたら」みたいな壮大なシミュレーションを延々やってる。表には出さないけど、心の中では結構ロマンチスト。",
    },
  },
  A: {
    key: "A",
    name: "解析者",
    en: "Analytical Mind",
    axes: ["論理", "行動"],
    color: "#2563EB",
    colorLight: "#EFF6FF",
    char: "🔍",
    tagline: "正確さの追求者",
    prompt:
      "私は「解析者タイプ」です。データと論理で判断を組み立てるのが得意で、正確さを重視します。会話では、根拠やソースを明示し、曖昧な表現を避け、数字や事実ベースで説明してください。",
    bestMatch: "E",
    code: "AN",
    reading: {
      intro:
        "あなたは「それって本当？」が口癖のタイプ。友達が「なんか最近これ流行ってるらしいよ」って言ったとき、すぐスマホで調べちゃうこと、あるでしょ？",
      aruaru: [
        "「たぶん」「なんとなく」って言葉を使う人にモヤッとする",
        "買い物の前にレビューを30分以上読み込む",
        "感覚で決めた判断が結局正しかったとき、ちょっと悔しい",
        "議論で「それソースある？」と言いたくなるのを必死に我慢してる",
        "部屋は散らかってても、PCのフォルダ構造だけはキレイ",
      ],
      love: "好きな人ができると、相手のSNSの過去投稿を徹底リサーチしがち。好きな人の「パターン」を把握してからアプローチしたい。でも分析しすぎて「好き」の感情を論理で処理しようとして、結局よくわからなくなることも。付き合ったら「覚えてくれてるんだ！」って相手が感動するくらい、細かいことを記憶してくれる。",
      school:
        "ノートの取り方に独自のルールがある。テスト前は「過去問の出題傾向」をスプレッドシートで分析してから勉強を始める。時間はかかるけど、一度理解したことは絶対に忘れない。",
      stress:
        "ストレスが溜まると「正論」が止まらなくなる。自分でも「今それ言わなくていいのに」と思いつつ、つい事実を突きつけてしまう。ひとりの時間に情報を整理すると落ち着く。",
      hidden:
        "実は感情の波がかなりある。表面はクールだけど、映画で泣いたり、推しに本気になったり、心の中ではかなり熱い。でもそれを人に見せるのが恥ずかしくて、いつも冷静なフリをしてる。",
    },
  },
  C: {
    key: "C",
    name: "探索者",
    en: "Creative Explorer",
    axes: ["感覚", "構想"],
    color: "#059669",
    colorLight: "#ECFDF5",
    char: "✨",
    tagline: "ひらめきの天才",
    prompt:
      "私は「探索者タイプ」です。直感とひらめきで新しい可能性を広げるのが得意です。会話では、いきなり正解を出さず一緒に考え、意外な視点や例え話を混ぜ、選択肢を広げてください。",
    bestMatch: "S",
    code: "CR",
    reading: {
      intro:
        "あなたは「こんなのどう？」が口癖のタイプ。会話してて急に全然違う話題に飛ぶのは、頭の中で繋がってるから。周りには唐突に見えるけど、自分の中ではちゃんと筋が通ってるんだよね？",
      aruaru: [
        "ひとつのことに集中するより、3つ同時にやってる方が調子いい",
        "「普通」って言われるのが一番テンション下がる",
        "思いついたアイデアをメモする前に次のアイデアが来て、最初のを忘れる",
        "話が脱線しまくるけど、最終的にはなぜかちゃんと着地する",
        "「それ関係なくない？」と言われた案が、後で一番良かったりする",
      ],
      love: "好きになるポイントが独特。見た目より「この人の考え方おもしろい」で落ちる。ありきたりなデートより、2人で知らない街を歩いたり、変な店を開拓したりする方がときめく。でも「飽きっぽい」と誤解されがち。飽きてるんじゃなくて、常に新しい一面を探してるだけなんだけどね。",
      school:
        "興味あるところだけ異常に詳しくて、先生を驚かせることがある。逆に興味ないところは本当にやらない。「やればできるのに」って言われ続ける人生。テスト前日に全然違うことに夢中になって焦るのもあるある。",
      stress:
        "ストレスが溜まると現実逃避モードに入る。ずっとスマホ見てたり、妄想に浸ったり、新しい趣味を始めたりする。目の前の問題から逃げてるわけじゃなくて、充電してるだけ。でも周りからは「サボってる」って見えるかも。",
      hidden:
        "実はめちゃくちゃ繊細。自由奔放に見えて、人の一言を何日も引きずってたりする。でもそれを表に出すのがダサいと思ってるから、いつも平気なフリをしてる。本当は「わかってくれる人」がすごく欲しい。",
    },
  },
  E: {
    key: "E",
    name: "推進者",
    en: "Action Builder",
    axes: ["感覚", "行動"],
    color: "#E11D48",
    colorLight: "#FFF1F2",
    char: "⚡",
    tagline: "まず動く行動派",
    prompt:
      "私は「推進者タイプ」です。スピードと実行力を重視し、まずやってみるタイプです。会話では、結論やアクションを最初に出し、長い説明より箇条書き、「次にやること」を明確にしてください。",
    bestMatch: "A",
    code: "EX",
    reading: {
      intro:
        "あなたは「とりあえずやってみよ」のタイプ。周りがまだ話し合ってる間に、もう手を動かし始めてることない？「考えるより先に体が動く」って自分でもわかってるでしょ？",
      aruaru: [
        "長い会議やミーティングが苦痛。「で、何するの？」って思ってる",
        "やったことないことほどワクワクする。失敗してもあまり引きずらない",
        "予定をギチギチに詰めがち。暇な時間が怖い",
        "「もうちょっと考えてから動いたら？」って言われるけど、考えたら動けなくなる",
        "友達との約束は「とりあえず○○に集合ね！」で決まりがち",
      ],
      love: "好きになったら一直線。駆け引きとか回りくどいのは苦手で「好き」って伝えちゃうタイプ。付き合ったらサプライズとか行動で愛情表現する。ただ、相手のペースを考えずにグイグイいきすぎて「重い」と思われることも。「待つ」のが一番苦手な恋愛スタイル。",
      school:
        "テスト勉強は「まず問題を解いてみて」わからないところだけ覚える逆引きスタイル。教科書を最初から読む気にはなれない。でもこのやり方が意外と効率良くて、短時間でそこそこの点数が取れちゃう。",
      stress:
        "ストレスが溜まると「とにかく何か動きたい」衝動に駆られる。掃除を始めたり、急に模様替えしたり、走りに行ったり。じっとしてると余計に落ち込むから、体を動かすことで回復するタイプ。",
      hidden:
        "実は「認めてほしい」気持ちがすごく強い。いつも元気に見えるけど、自分のやったことを誰にも気づいてもらえないとき、密かに凹んでる。「すごいね」の一言がエネルギー源。もっと言ってほしい。",
    },
  },
};

const COMPAT = {
  SC: {
    star: true,
    text: "設計者の戦略 × 探索者のひらめき＝最強コンビ！2人でいると誰も思いつかなかったプランが生まれる。",
    friction: "設計者が計画を絞りたいときに、探索者がまだ広げたくなる。タイミングが合えば無敵。",
  },
  AE: {
    star: true,
    text: "解析者の正確さ × 推進者のスピード＝速くて間違いない最高のペア！",
    friction: "解析者の「もうちょっと調べたい」と推進者の「もう動きたい」がぶつかりがち。",
  },
  SA: {
    star: false,
    text: "計画力×情報力。2人が納得した答えはまず間違いない。ただし慎重すぎて動き出すのに時間がかかることも。",
    friction: "完璧な計画ができても、誰も実行しない問題が発生しがち。",
  },
  SE: {
    star: false,
    text: "設計者が「こっち！」と指した方向に推進者がダッシュ。アイデアから結果までが一番速いペア。",
    friction: "推進者が全部聞く前に走り出しちゃうことがある。",
  },
  AC: {
    star: false,
    text: "一番タイプが違う2人。だからこそ「え、そういう見方する？」という発見が一番多い刺激的な関係。",
    friction: "最初はお互いの考え方が理解しにくい。でも信頼できたら最強。",
  },
  CE: {
    star: false,
    text: "アイデア出すのも試すのも爆速。新しいこと始めるときは最強。ノリと勢いで突破する力がある。",
    friction: "2人とも振り返るのが苦手で、間違った方向に全速力で走り続けるリスクあり。",
  },
};

const QUESTIONS = [
  {
    id: 1,
    text: "友達と週末の予定を決めるとき、あなたは？",
    options: [
      { text: "「○○とか面白そうじゃない？」とアイデアをどんどん出す", type: "C", a1: -1, a2: 1 },
      { text: "「とりあえず集合しよ！」現地で考えればOK", type: "E", a1: -1, a2: -1 },
      { text: "何時にどこ集合がベストか、ざっくりプランを立てる", type: "S", a1: 1, a2: 1 },
      { text: "予算と移動時間を調べて、コスパ最強の案を出す", type: "A", a1: 1, a2: -1 },
    ],
  },
  {
    id: 2,
    text: "AIチャットを使うとき、一番やりがちなのは？",
    options: [
      { text: "「このアイデアどう思う？」って相談する", type: "C", a1: -1, a2: 1 },
      { text: "面白いこと聞いて遊ぶ・ネタ探し", type: "E", a1: -1, a2: -1 },
      { text: "レポートや文章の構成を一緒に考える", type: "S", a1: 1, a2: 1 },
      { text: "わからないことの正確な答えをサクッと調べる", type: "A", a1: 1, a2: -1 },
    ],
  },
  {
    id: 3,
    text: "グループLINEで意見がバラバラ。あなたは？",
    options: [
      { text: "全然違う案を出して空気を変える", type: "C", a1: -1, a2: 1 },
      { text: "「もういいからこれにしよ！」って決めにいく", type: "E", a1: -1, a2: -1 },
      { text: "そもそも何がしたかったのか、話を最初に戻す", type: "S", a1: 1, a2: 1 },
      { text: "それぞれの案のメリデメを並べて比較する", type: "A", a1: 1, a2: -1 },
    ],
  },
  {
    id: 4,
    text: "新しいゲームやアプリを始めるとき、どうする？",
    options: [
      { text: "上手い人の動画を見て、自分なりのスタイルを探す", type: "C", a1: -1, a2: 1 },
      { text: "とりあえず触って、やりながら覚える", type: "E", a1: -1, a2: -1 },
      { text: "基本の仕組みやルールを最初にしっかり理解する", type: "S", a1: 1, a2: 1 },
      { text: "攻略サイトで効率いい進め方を調べてから始める", type: "A", a1: 1, a2: -1 },
    ],
  },
  {
    id: 5,
    text: "友達に相談されたとき、つい最初にやることは？",
    options: [
      { text: "「え、それってつまりこういうこと？」と解釈を広げる", type: "C", a1: -1, a2: 1 },
      { text: "「で、どうしたいの？」とアクションを聞く", type: "E", a1: -1, a2: -1 },
      { text: "「そもそも原因は何だと思う？」と根本を探る", type: "S", a1: 1, a2: 1 },
      { text: "「具体的に何があったか教えて」と事実を確認する", type: "A", a1: 1, a2: -1 },
    ],
  },
  {
    id: 6,
    text: "SNSを見てるとき、一番つい見ちゃうのは？",
    options: [
      { text: "面白い発想や独特なセンスの投稿", type: "C", a1: -1, a2: 1 },
      { text: "「やってみた」系の挑戦動画", type: "E", a1: -1, a2: -1 },
      { text: "業界の裏側や構造を解説する長文", type: "S", a1: 1, a2: 1 },
      { text: "データや検証系のわかりやすい比較コンテンツ", type: "A", a1: 1, a2: -1 },
    ],
  },
  {
    id: 7,
    text: "一番テンション上がるのはどんなとき？",
    weight: 2,
    options: [
      { text: "誰も思いつかなかったアイデアがひらめいた！", type: "C", a1: -2, a2: 2 },
      { text: "やってみたことが実際にうまくいった！", type: "E", a1: -2, a2: -2 },
      { text: "バラバラだった情報がひとつにつながった！", type: "S", a1: 2, a2: 2 },
      { text: "計画通りに全部キレイに片付いた！", type: "A", a1: 2, a2: -2 },
    ],
  },
];

// ─── Helpers ────────────────────────────────────────────────────────────────

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function getCompat(a, b) {
  return COMPAT[[a, b].sort().join("")] || null;
}

function encodeResult(typeKey, x, y) {
  const cx = (Math.max(-9, Math.min(9, x)) + 9).toString(36);
  const cy = (Math.max(-9, Math.min(9, y)) + 9).toString(36);
  return `${TYPES[typeKey].code}${cx}${cy}`;
}

function decodeResult(code) {
  if (!code || code.length < 4) return null;
  const prefix = code.slice(0, 2).toUpperCase();
  const entry = Object.entries(TYPES).find(([, t]) => t.code === prefix);
  if (!entry) return null;
  const x = parseInt(code[2], 36) - 9;
  const y = parseInt(code[3], 36) - 9;
  if (isNaN(x) || isNaN(y)) return null;
  return { typeKey: entry[0], a1: x, a2: y };
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function AxisBar({ left, right, leftColor, rightColor, value, animated }) {
  const raw = ((9 - value) / 18) * 100;
  const lp = Math.max(18, Math.min(82, Math.round(raw)));
  const rp = 100 - lp;
  const dominant = lp >= rp ? "l" : "r";
  const pct = Math.max(lp, rp);

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <div>
          <span style={{ fontSize: 14, fontWeight: dominant === "l" ? 700 : 400, color: dominant === "l" ? leftColor : "#ccc" }}>
            {left}
          </span>
          {dominant === "l" && (
            <span style={{ fontSize: 22, fontWeight: 800, color: leftColor, marginLeft: 6 }}>{pct}%</span>
          )}
        </div>
        <div>
          {dominant === "r" && (
            <span style={{ fontSize: 22, fontWeight: 800, color: rightColor, marginRight: 6 }}>{pct}%</span>
          )}
          <span style={{ fontSize: 14, fontWeight: dominant === "r" ? 700 : 400, color: dominant === "r" ? rightColor : "#ccc" }}>
            {right}
          </span>
        </div>
      </div>
      <div style={{ height: 16, borderRadius: 8, background: "#F3F4F6", overflow: "hidden", display: "flex" }}>
        <div
          style={{
            width: animated ? `${lp}%` : "50%",
            height: "100%",
            background: leftColor,
            borderRadius: "8px 0 0 8px",
            transition: "width 1s cubic-bezier(0.34,1.56,0.64,1)",
          }}
        />
        <div
          style={{
            width: animated ? `${rp}%` : "50%",
            height: "100%",
            background: rightColor,
            borderRadius: "0 8px 8px 0",
            transition: "width 1s cubic-bezier(0.34,1.56,0.64,1)",
          }}
        />
      </div>
    </div>
  );
}

function CopyBtn({ text, label, color }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <button
      onClick={handleCopy}
      style={{
        width: "100%",
        background: copied ? "#ECFDF5" : `${color}12`,
        color: copied ? "#059669" : color,
        border: `2px solid ${copied ? "#05966930" : `${color}30`}`,
        borderRadius: 14,
        padding: "13px 20px",
        fontSize: 14,
        fontWeight: 700,
        cursor: "pointer",
        transition: "all 0.2s",
      }}
    >
      {copied ? "✅ コピーした！" : label}
    </button>
  );
}

function Section({ emoji, title, children, bg }) {
  return (
    <div
      style={{
        background: bg || "#fff",
        borderRadius: 20,
        padding: "20px 22px",
        boxShadow: "0 2px 16px rgba(0,0,0,0.05)",
        marginBottom: 12,
      }}
    >
      <p style={{ fontSize: 14, fontWeight: 800, color: "#1E1B4B", margin: "0 0 12px" }}>
        {emoji} {title}
      </p>
      {children}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

const FONT = 'system-ui,-apple-system,"Hiragino Sans",sans-serif';
const TEXT_COLOR = "#52525B";

export default function ThinkType() {
  const [phase, setPhase] = useState("start");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [typeScores, setTypeScores] = useState({ S: 0, A: 0, C: 0, E: 0 });
  const [axis1, setAxis1] = useState(0);
  const [axis2, setAxis2] = useState(0);
  const [fade, setFade] = useState(true);
  const [hoveredOption, setHoveredOption] = useState(null);
  const [barsAnimated, setBarsAnimated] = useState(false);
  const [friendCode, setFriendCode] = useState("");
  const [friendResult, setFriendResult] = useState(null);
  const [friendError, setFriendError] = useState(false);

  const shuffledQuestions = useMemo(
    () => QUESTIONS.map((q) => ({ ...q, options: shuffle(q.options) })),
    []
  );

  const resultType = useMemo(() => {
    if (axis1 > 0 && axis2 > 0) return "S";
    if (axis1 > 0 && axis2 <= 0) return "A";
    if (axis1 <= 0 && axis2 > 0) return "C";
    return "E";
  }, [axis1, axis2]);

  const barScores = useMemo(() => {
    const raw = { ...typeScores };
    const main = resultType;
    const total = Object.values(raw).reduce((s, v) => s + v, 0) || 1;
    const boosted = {};
    Object.keys(raw).forEach((k) => {
      boosted[k] =
        k === main
          ? Math.min(90, Math.round((raw[k] / total) * 100) + 25)
          : Math.max(3, Math.round((raw[k] / total) * 100) - 8);
    });
    const sum = Object.values(boosted).reduce((s, v) => s + v, 0);
    if (sum !== 100) boosted[main] += 100 - sum;
    return boosted;
  }, [typeScores, resultType]);

  const myCode = useMemo(() => encodeResult(resultType, axis1, axis2), [resultType, axis1, axis2]);

  const handleAnswer = useCallback(
    (option) => {
      setFade(false);
      setTimeout(() => {
        const weight = QUESTIONS[questionIndex].weight || 1;
        setTypeScores((prev) => ({ ...prev, [option.type]: prev[option.type] + weight }));
        setAxis1((prev) => prev + option.a1);
        setAxis2((prev) => prev + option.a2);

        if (questionIndex < QUESTIONS.length - 1) {
          setQuestionIndex((i) => i + 1);
        } else {
          setPhase("result");
          setTimeout(() => setBarsAnimated(true), 150);
        }
        setFade(true);
        setHoveredOption(null);
      }, 180);
    },
    [questionIndex]
  );

  const handleShare = () => {
    const t = TYPES[resultType];
    const text = `${t.char} AI思考タイプ診断「ThinkType」\n\n私は【${t.name}】タイプ！\n${t.axes[0]} × ${t.axes[1]}\n\n結果コード：${myCode}\n友達のコードを入力すると相性がわかる！\n\nあなたの思考OSは？`;
    window.open(
      `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent("https://thinktype.me")}`,
      "_blank"
    );
  };

  const handleRetry = () => {
    setPhase("start");
    setQuestionIndex(0);
    setTypeScores({ S: 0, A: 0, C: 0, E: 0 });
    setAxis1(0);
    setAxis2(0);
    setFade(true);
    setBarsAnimated(false);
    setFriendCode("");
    setFriendResult(null);
    setFriendError(false);
  };

  const checkFriendCompat = () => {
    const decoded = decodeResult(friendCode.trim());
    if (decoded) {
      setFriendResult(decoded);
      setFriendError(false);
    } else {
      setFriendResult(null);
      setFriendError(true);
    }
  };

  // ─── START SCREEN ──────────────────────────────────────────────────────────

  if (phase === "start") {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
          fontFamily: FONT,
        }}
      >
        <div style={{ maxWidth: 400, width: "100%", textAlign: "center" }}>
          <h1 style={{ fontSize: 40, fontWeight: 800, color: "#18181B", margin: "0 0 6px", letterSpacing: -1 }}>
            Think<span style={{ color: "#8B5CF6" }}>Type</span>
          </h1>
          <p style={{ fontSize: 14, color: "#71717A", margin: "0 0 32px" }}>AI思考タイプ診断</p>

          <div
            style={{
              background: "#18181B",
              borderRadius: 16,
              padding: "28px 24px",
              marginBottom: 24,
              textAlign: "left",
            }}
          >
            <p style={{ fontSize: 18, fontWeight: 700, color: "#fff", margin: "0 0 12px", lineHeight: 1.5 }}>
              あなたの<span style={{ color: "#A78BFA" }}>「思考のクセ」</span>を<br />
              AIに覚えさせよう
            </p>
            <p style={{ fontSize: 13, color: "#A1A1AA", lineHeight: 1.7, margin: 0 }}>
              7問答えるだけで思考タイプを診断。結果をChatGPTやGeminiに貼ると、
              <strong style={{ color: "#E5E7EB" }}>あなた専用の返答</strong>をしてくれるようになる。
            </p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 24 }}>
            {Object.values(TYPES).map((t) => (
              <div
                key={t.key}
                style={{
                  background: "#FAFAFA",
                  borderRadius: 12,
                  padding: "16px 12px",
                  textAlign: "left",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <span style={{ fontSize: 28 }}>{t.char}</span>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: "#18181B" }}>{t.name}</div>
                  <div style={{ fontSize: 11, color: "#A1A1AA" }}>{t.axes[0]} × {t.axes[1]}</div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 12, justifyContent: "center", marginBottom: 28 }}>
            <span style={{ fontSize: 12, color: "#71717A" }}>友達と相性診断</span>
            <span style={{ color: "#E5E5E5" }}>|</span>
            <span style={{ fontSize: 12, color: "#71717A" }}>AIに貼れる</span>
            <span style={{ color: "#E5E5E5" }}>|</span>
            <span style={{ fontSize: 12, color: "#71717A" }}>約2分</span>
          </div>

          <button
            onClick={() => setPhase("quiz")}
            onMouseEnter={(e) => { e.currentTarget.style.background = "#7C3AED"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "#8B5CF6"; }}
            style={{
              background: "#8B5CF6",
              color: "#fff",
              border: "none",
              borderRadius: 12,
              padding: "16px 0",
              fontSize: 16,
              fontWeight: 700,
              cursor: "pointer",
              width: "100%",
              transition: "all 0.2s",
            }}
          >
            診断スタート
          </button>
          <p style={{ fontSize: 11, color: "#D4D4D8", marginTop: 12 }}>全7問・登録不要・完全無料</p>
        </div>
      </div>
    );
  }

  // ─── QUIZ SCREEN ───────────────────────────────────────────────────────────

  if (phase === "quiz") {
    const q = shuffledQuestions[questionIndex];
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#FAFAFA",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
          fontFamily: FONT,
        }}
      >
        <div
          style={{
            maxWidth: 480,
            width: "100%",
            opacity: fade ? 1 : 0,
            transition: "opacity 0.18s ease",
          }}
        >
          {/* Progress dots */}
          <div style={{ display: "flex", gap: 6, marginBottom: 28, justifyContent: "center" }}>
            {QUESTIONS.map((_, i) => (
              <div
                key={i}
                style={{
                  width: i === questionIndex ? 28 : 8,
                  height: 8,
                  borderRadius: 4,
                  background: i <= questionIndex ? "#8B5CF6" : "#E5E5E5",
                  transition: "all 0.3s",
                }}
              />
            ))}
          </div>

          <div style={{ textAlign: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: "#A1A1AA" }}>
              Q{q.id} / {QUESTIONS.length}
              {q.weight === 2 ? "  ⭐ 重要な質問" : ""}
            </span>
          </div>

          <div
            style={{
              background: "#fff",
              borderRadius: 20,
              padding: "28px 24px",
              boxShadow: "0 2px 16px rgba(0,0,0,0.06)",
            }}
          >
            <h2
              style={{
                fontSize: 17,
                fontWeight: 700,
                color: "#1E1B4B",
                lineHeight: 1.7,
                margin: "0 0 24px",
                textAlign: "center",
              }}
            >
              {q.text}
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {q.options.map((opt, i) => {
                const isHovered = hoveredOption === i;
                return (
                  <button
                    key={i}
                    onClick={() => handleAnswer(opt)}
                    onMouseEnter={() => setHoveredOption(i)}
                    onMouseLeave={() => setHoveredOption(null)}
                    style={{
                      background: isHovered ? "#F5F3FF" : "#FAFAFA",
                      border: isHovered ? "2px solid #8B5CF6" : "2px solid transparent",
                      borderRadius: 14,
                      padding: "14px 18px",
                      fontSize: 14,
                      color: isHovered ? "#4C1D95" : TEXT_COLOR,
                      textAlign: "left",
                      cursor: "pointer",
                      transition: "all 0.15s",
                      lineHeight: 1.6,
                      fontWeight: isHovered ? 600 : 400,
                    }}
                  >
                    {opt.text}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ─── RESULT SCREEN ─────────────────────────────────────────────────────────

  const mainType = TYPES[resultType];
  const bestMatchType = TYPES[mainType.bestMatch];
  const compatData = getCompat(resultType, mainType.bestMatch);
  const reading = mainType.reading;

  return (
    <div
      style={{
        minHeight: "100vh",
        background: `linear-gradient(180deg,${mainType.colorLight} 0%,#FAFAFA 15%)`,
        padding: "36px 20px 48px",
        fontFamily: FONT,
      }}
    >
      <div style={{ maxWidth: 440, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <p style={{ fontSize: 12, color: "#A1A1AA", letterSpacing: 1.5, margin: "0 0 4px" }}>
            YOUR THINKING OS
          </p>
          <div style={{ fontSize: 64, marginBottom: 4 }}>{mainType.char}</div>
          <h1 style={{ fontSize: 42, fontWeight: 800, color: mainType.color, margin: "0 0 2px" }}>
            {mainType.name}
          </h1>
          <p style={{ fontSize: 14, color: `${mainType.color}99`, fontWeight: 600, margin: "0 0 4px" }}>
            {mainType.tagline}
          </p>
          <p style={{ fontSize: 13, color: "#A1A1AA", margin: "0 0 14px" }}>{mainType.en}</p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            {mainType.axes.map((ax, i) => (
              <span key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {i > 0 && <span style={{ color: "#D4D4D8" }}>×</span>}
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 700,
                    color: mainType.color,
                    background: mainType.colorLight,
                    padding: "5px 16px",
                    borderRadius: 20,
                    border: `1.5px solid ${mainType.color}30`,
                  }}
                >
                  {ax}
                </span>
              </span>
            ))}
          </div>
        </div>

        {/* Axis Breakdown */}
        <Section emoji="🧬" title="あなたの思考タイプを分解">
          <AxisBar
            left="感覚派" right="論理派"
            leftColor="#E11D48" rightColor="#2563EB"
            value={barsAnimated ? axis1 : 0} animated={barsAnimated}
          />
          <AxisBar
            left="行動派" right="構想派"
            leftColor="#F59E0B" rightColor="#059669"
            value={barsAnimated ? axis2 : 0} animated={barsAnimated}
          />
        </Section>

        {/* Reading sections */}
        <Section emoji="💬" title="あなたはこういう人">
          <p style={{ fontSize: 14, color: TEXT_COLOR, lineHeight: 1.9, margin: 0 }}>{reading.intro}</p>
        </Section>

        <Section emoji="💡" title="こんなとこ、あるでしょ？">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {reading.aruaru.map((item, i) => (
              <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <span style={{ color: mainType.color, fontSize: 16, lineHeight: "24px", flexShrink: 0 }}>✔</span>
                <p style={{ fontSize: 13, color: TEXT_COLOR, lineHeight: 1.7, margin: 0 }}>{item}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section emoji="💕" title="恋愛・友情では">
          <p style={{ fontSize: 13, color: TEXT_COLOR, lineHeight: 1.9, margin: 0 }}>{reading.love}</p>
        </Section>

        <Section emoji="📚" title="勉強・仕事では">
          <p style={{ fontSize: 13, color: TEXT_COLOR, lineHeight: 1.9, margin: 0 }}>{reading.school}</p>
        </Section>

        <Section emoji="😮‍💨" title="ストレス溜まると…">
          <p style={{ fontSize: 13, color: TEXT_COLOR, lineHeight: 1.9, margin: 0 }}>{reading.stress}</p>
        </Section>

        <Section
          emoji="🤫"
          title="実は隠してる一面"
          bg={`linear-gradient(135deg,${mainType.colorLight},#F5F3FF)`}
        >
          <p style={{ fontSize: 13, color: TEXT_COLOR, lineHeight: 1.9, margin: 0 }}>{reading.hidden}</p>
        </Section>

        {/* 4-type distribution */}
        <Section emoji="📊" title="4タイプ分布">
          {Object.entries(TYPES).map(([key, t]) => {
            const pct = barScores[key];
            const isMain = key === resultType;
            return (
              <div key={key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0" }}>
                <span style={{ fontSize: 24, width: 32, textAlign: "center" }}>{t.char}</span>
                <span style={{ fontSize: 13, fontWeight: isMain ? 800 : 400, color: isMain ? t.color : "#A1A1AA", width: 52 }}>
                  {t.name}
                </span>
                <div style={{ flex: 1, height: 14, background: "#F3F4F6", borderRadius: 7, overflow: "hidden" }}>
                  <div
                    style={{
                      width: barsAnimated ? `${pct}%` : "0%",
                      height: "100%",
                      background: isMain ? t.color : "#E5E5E5",
                      borderRadius: 7,
                      transition: "width 1s cubic-bezier(0.34,1.56,0.64,1) 0.2s",
                    }}
                  />
                </div>
                <span style={{ fontSize: 16, fontWeight: 800, color: isMain ? t.color : "#D4D4D8", width: 44, textAlign: "right" }}>
                  {pct}%
                </span>
              </div>
            );
          })}
        </Section>

        {/* AI Prompt */}
        <div
          style={{
            background: `linear-gradient(135deg,${mainType.colorLight},#F5F3FF)`,
            borderRadius: 20,
            padding: 22,
            border: `2px solid ${mainType.color}15`,
            marginBottom: 12,
          }}
        >
          <p style={{ fontSize: 14, fontWeight: 800, color: "#1E1B4B", margin: "0 0 6px" }}>
            🤖 AIを自分専用にする
          </p>
          <p style={{ fontSize: 12, color: "#71717A", lineHeight: 1.6, margin: "0 0 12px" }}>
            下のテキストをコピーして、ChatGPTやGeminiの「カスタム指示」に貼るだけ！
          </p>
          <div
            style={{
              background: "rgba(255,255,255,0.8)",
              borderRadius: 12,
              padding: "12px 14px",
              marginBottom: 12,
              fontSize: 12,
              color: TEXT_COLOR,
              lineHeight: 1.7,
              border: "1px solid #E5E7EB",
            }}
          >
            {mainType.prompt}
          </div>
          <CopyBtn text={mainType.prompt} label="📋 AI用プロンプトをコピー" color={mainType.color} />
        </div>

        {/* Best compatibility */}
        <Section emoji="🤝" title="相性ベスト">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <span style={{ fontSize: 32 }}>{mainType.char}</span>
            <span style={{ fontSize: 24, fontWeight: 800, color: mainType.color }}>{mainType.name}</span>
            <span style={{ fontSize: 18, color: "#D4D4D8" }}>×</span>
            <span style={{ fontSize: 32 }}>{bestMatchType.char}</span>
            <span style={{ fontSize: 24, fontWeight: 800, color: bestMatchType.color }}>{bestMatchType.name}</span>
            {compatData?.star && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  color: "#F59E0B",
                  background: "#FFF8E7",
                  padding: "3px 10px",
                  borderRadius: 12,
                }}
              >
                ⭐
              </span>
            )}
          </div>
          {compatData && (
            <>
              <p style={{ fontSize: 13, color: TEXT_COLOR, lineHeight: 1.8, margin: "0 0 12px" }}>
                {compatData.text}
              </p>
              <div
                style={{
                  background: "#FFF5F5",
                  borderRadius: 12,
                  padding: "10px 14px",
                  fontSize: 12,
                  color: "#E11D48",
                  lineHeight: 1.6,
                }}
              >
                ⚡ {compatData.friction}
              </div>
            </>
          )}
        </Section>

        {/* Friend compatibility */}
        <div
          style={{
            background: "linear-gradient(135deg,#F5F3FF,#FDF2F8)",
            borderRadius: 20,
            padding: 22,
            border: "2px solid #E9D5FF",
            marginBottom: 12,
          }}
        >
          <p style={{ fontSize: 14, fontWeight: 800, color: "#1E1B4B", margin: "0 0 6px" }}>
            👯 友達と相性診断
          </p>
          <p style={{ fontSize: 12, color: "#71717A", margin: "0 0 10px", lineHeight: 1.6 }}>
            あなたのコードを友達に送ろう！友達のコードを入れると相性がわかるよ
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <span style={{ fontSize: 12, color: "#A1A1AA" }}>私のコード</span>
            <span
              style={{
                fontSize: 18,
                fontWeight: 800,
                color: "#8B5CF6",
                background: "#F5F3FF",
                padding: "6px 16px",
                borderRadius: 10,
                letterSpacing: 2,
                fontFamily: "monospace",
              }}
            >
              {myCode}
            </span>
            <CopyBtn text={myCode} label="コピー" color="#8B5CF6" />
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <input
              value={friendCode}
              onChange={(e) => {
                setFriendCode(e.target.value);
                setFriendError(false);
                setFriendResult(null);
              }}
              placeholder="友達のコードを入力..."
              style={{
                flex: 1,
                padding: "12px 16px",
                borderRadius: 12,
                border: friendError ? "2px solid #EF4444" : "2px solid #E5E7EB",
                fontSize: 14,
                fontFamily: "monospace",
                letterSpacing: 2,
                outline: "none",
                background: "#fff",
              }}
            />
            <button
              onClick={checkFriendCompat}
              style={{
                background: "#8B5CF6",
                color: "#fff",
                border: "none",
                borderRadius: 12,
                padding: "12px 20px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              診断
            </button>
          </div>

          {friendError && (
            <p style={{ fontSize: 12, color: "#EF4444", margin: "0 0 8px" }}>
              コードが正しくないよ！もう一度確認してね
            </p>
          )}

          {friendResult && (() => {
            const ft = TYPES[friendResult.typeKey];
            const fCompat = getCompat(resultType, friendResult.typeKey);
            return (
              <div style={{ background: "rgba(255,255,255,0.8)", borderRadius: 14, padding: 16, marginTop: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 28 }}>{mainType.char}</span>
                  <span style={{ fontWeight: 800, color: mainType.color }}>{mainType.name}</span>
                  <span style={{ color: "#D4D4D8" }}>×</span>
                  <span style={{ fontSize: 28 }}>{ft.char}</span>
                  <span style={{ fontWeight: 800, color: ft.color }}>{ft.name}</span>
                  {fCompat?.star && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 800,
                        color: "#F59E0B",
                        background: "#FFF8E7",
                        padding: "2px 8px",
                        borderRadius: 10,
                      }}
                    >
                      ⭐ BEST
                    </span>
                  )}
                </div>
                {fCompat ? (
                  <>
                    <p style={{ fontSize: 13, color: TEXT_COLOR, lineHeight: 1.7, margin: "0 0 8px" }}>
                      {fCompat.text}
                    </p>
                    <p style={{ fontSize: 12, color: "#E11D48", margin: 0 }}>⚡ {fCompat.friction}</p>
                  </>
                ) : resultType === friendResult.typeKey ? (
                  <p style={{ fontSize: 13, color: TEXT_COLOR, lineHeight: 1.7, margin: 0 }}>
                    同じタイプ！考え方が似てるから話が合うけど、同じ盲点も共有しやすい。お互いの「当たり前」を疑える第三者がいると最強。
                  </p>
                ) : null}
              </div>
            );
          })()}
        </div>

        {/* Action buttons */}
        <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
          <button
            onClick={handleShare}
            onMouseEnter={(e) => { e.currentTarget.style.transform = "scale(1.02)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
            style={{
              flex: 1,
              background: `linear-gradient(135deg,${mainType.color},${mainType.color}CC)`,
              color: "#fff",
              border: "none",
              borderRadius: 50,
              padding: "16px 0",
              fontSize: 15,
              fontWeight: 800,
              cursor: "pointer",
              boxShadow: `0 4px 16px ${mainType.color}40`,
              transition: "transform 0.15s",
            }}
          >
            Xでシェアする
          </button>
          <button
            onClick={handleRetry}
            onMouseEnter={(e) => { e.currentTarget.style.background = "#EAEAEA"; e.currentTarget.style.color = "#666"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "#F5F5F5"; e.currentTarget.style.color = "#A1A1AA"; }}
            style={{
              background: "#F5F5F5",
              color: "#A1A1AA",
              border: "none",
              borderRadius: 50,
              padding: "16px 24px",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            もう一度
          </button>
        </div>

        <p style={{ textAlign: "center", fontSize: 11, color: "#D4D4D8", marginTop: 20 }}>
          Think<span style={{ color: "#8B5CF6" }}>Type</span> — AI思考タイプ診断
        </p>
      </div>
    </div>
  );
}
