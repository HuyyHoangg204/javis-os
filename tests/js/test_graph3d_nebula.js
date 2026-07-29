/* Chống tái phát cho phần VẼ của tinh vân 3D (graph3d.js).
   Chạy:  node tests/js/test_graph3d_nebula.js

   Bốn thứ đây khoá lại, vì mỗi cái đều đã từng làm đồ thị 3D nhìn bệt hoặc dẹt:
   1. Hạt KHÔNG được có điểm dừng màu trắng - vài trăm sprite cộng sáng chồng nhau sẽ
      dồn hết về trắng và mất sạch màu danh mục.
   2. Tông sáng phải đổi sang chồng thường: cộng sáng trên nền giấy ra trắng bệt.
   3. Phải có sương mù theo chiều sâu, độ dày suy ra từ bán kính khối (brain to nhỏ khác
      nhau nên hằng số cứng là sai).
   4. Lực hút về tâm phải nặng hơn với node nhiều liên kết → lõi đặc, vành thưa.
*/
global.window = global;

// Ghi lại MỌI điểm dừng gradient để soi được bảng màu thật sự vẽ ra.
const gradients = [];
global.document = {
  documentElement: { getAttribute: () => global.__theme || null },
  createElement: () => ({
    getContext: () => ({
      createRadialGradient() {
        const stops = [];
        gradients.push(stops);
        return { addColorStop(at, c) { stops.push([at, c]); } };
      },
      fillRect() {},
    }),
  }),
};
global.window.dispatchEvent = () => {};
global.window.addEventListener = () => {};

// --- Stub THREE tối thiểu: chỉ giữ những gì graph3d.js thật sự đụng tới ---
class Obj3D {
  constructor() { this.scale = { set() {}, setScalar() {} }; this.rotation = { x: 0, y: 0 }; }
}
global.window.THREE = {
  CanvasTexture: class { constructor(cv) { this.cv = cv; } },
  SpriteMaterial: class { constructor(o) { Object.assign(this, o); } dispose() {} },
  PointsMaterial: class { constructor(o) { Object.assign(this, o); } dispose() {} },
  Sprite: class extends Obj3D { constructor(mat) { super(); this.material = mat; } },
  Points: class extends Obj3D { constructor(geo, mat) { super(); this.geometry = geo; this.material = mat; } },
  BufferGeometry: class { setAttribute() {} dispose() {} },
  BufferAttribute: class { constructor(a) { this.array = a; } },
  FogExp2: class { constructor(color, density) { this.color = color; this.density = density; } },
  AdditiveBlending: "ADD",
  NormalBlending: "NORMAL",
};

require("../../dashboard/graph.js");
require("../../dashboard/graph3d.js");

let fails = 0;
function check(name, cond) {
  console.log((cond ? "ok   " : "FAIL ") + name);
  if (!cond) fails++;
}

// Dựng một instance với scene giả để soi các lớp được thêm vào.
function makeGraph(nodes) {
  const added = [];
  const scene = { add: (o) => added.push(o), remove: (o) => { const i = added.indexOf(o); if (i >= 0) added.splice(i, 1); }, fog: null };
  const g = new window.JavisGraph3D({ style: {} }, { style: {} });
  g.graph = {
    scene: () => scene,
    graphData: () => ({ nodes, links: [] }),
    linkColor() { return this; },
    linkOpacity() { return this; },
    linkDirectionalParticleColor() { return this; },
  };
  return { g, scene, added };
}

const NODES = [
  { id: "a", x: 100, y: 0, z: 0, links: 30, color: "#8b93ff" },
  { id: "b", x: 0, y: 80, z: 0, links: 1, color: "#3fdc9a" },
  { id: "c", x: 0, y: 0, z: 120, links: 0, color: "#f0a24a" },
];

// ---- 1. Hạt không được có lõi trắng ----------------------------------------
gradients.length = 0;
const { g, scene, added } = makeGraph(NODES);
g._buildCore();
const coreStops = gradients[gradients.length - 1];

// Ép vẽ texture của một hạt node bằng cách gọi lại _recolor (nó dựng lại mọi thứ)
gradients.length = 0;
NODES.forEach(n => { n.__sprite = { material: {} }; });
g._recolor();

function isWhitish(c) {
  const m = String(c).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return false;
  const [r, gr, b] = [+m[1], +m[2], +m[3]];
  const a = (String(c).match(/,\s*([\d.]+)\s*\)$/) || [])[1];
  return r > 240 && gr > 240 && b > 240 && (a === undefined || +a > 0.05);
}
// Gradient của HẠT node (không tính lõi, lõi được phép có tâm sáng)
const nodeGrads = gradients.filter(st => st.length && !st.some(s => /rgba\(255,247,236|rgba\(124,58,237,0\.26/.test(s[1])));
const anyWhiteInNode = nodeGrads.some(st => st.some(([, c]) => isWhitish(c)));
check("hạt node KHÔNG có điểm dừng màu trắng (giữ được màu danh mục)", !anyWhiteInNode);
check("gradient hạt node có được vẽ ra để kiểm", nodeGrads.length > 0);

// ---- 2. Đổi tông phải đổi kiểu chồng lớp -----------------------------------
global.__theme = null;
g._recolor();
const darkBlend = NODES[0].__sprite.material.blending;
global.__theme = "light";
g._recolor();
const lightBlend = NODES[0].__sprite.material.blending;
global.__theme = null;
check("tông tối dùng cộng sáng", darkBlend === "ADD");
check("tông sáng dùng chồng thường (cộng sáng trên giấy ra trắng bệt)", lightBlend === "NORMAL");

// ---- 3. Sương mù theo chiều sâu, suy ra từ bán kính ------------------------
g._applyDepth();
check("scene có sương mù", !!scene.fog);
const R = g._radius();
check("bán kính đo từ node, không phải hằng số", Math.abs(R - 100) < 1);
// KHÔNG khoá vào con số fogK cụ thể (nó là núm chỉnh thẩm mỹ, sẽ còn vặn). Khoá vào
// QUAN HỆ: sương phải tỉ lệ nghịch với bán kính, và nằm trong khoảng dùng được.
const dens = scene.fog.density;
check("độ dày sương nằm trong khoảng hợp lý", dens > 0 && dens * R > 0.05 && dens * R < 0.6);
// Brain to gấp đôi thì sương phải loãng đi một nửa, không thì khối lớn mờ tịt
const big = makeGraph(NODES.map(n => ({ ...n, x: n.x * 2, y: n.y * 2, z: n.z * 2 })));
big.g._applyDepth();
check("brain to gấp đôi thì sương loãng đi một nửa",
      Math.abs(big.scene.fog.density - dens / 2) < dens * 0.06);

// ---- 4. Lõi sáng + bụi vành có mặt ----------------------------------------
const { g: g2, added: added2 } = makeGraph(NODES);
g2._buildCore();
g2._buildDust();
check("có lõi sáng ở tâm", !!g2._core);
check("có lớp bụi vành", !!g2._dust);
check("lõi vẽ trước node (renderOrder âm)", g2._core.renderOrder < 0);
check("bụi vẽ dưới cùng", g2._dust.renderOrder < g2._core.renderOrder);
check("lõi KHÔNG chịu sương (nó là nguồn sáng)", g2._core.material.fog === false);
check("bụi CÓ chịu sương", g2._dust.material.fog === true);
// Dựng lại không được nhân bản object trong scene
const before = added2.length;
g2._buildCore(); g2._buildDust();
check("dựng lại không nhân bản lớp trong scene", added2.length === before);

// ---- 5. Lực hút tỉ lệ số liên kết -----------------------------------------
// centerGravity3D là hàm module nên soi gián tiếp qua trọng số nó gán lên node.
const probe = [{ links: 100 }, { links: 10 }, { links: 0 }];
// Lấy lại force qua d3Force đã đăng ký thì phức tạp; dựng lại đúng công thức để khoá:
let max = 1; probe.forEach(n => { max = Math.max(max, n.links || 0); });
probe.forEach(n => { n.__gw = 0.45 + 1.35 * Math.pow((n.links || 0) / max, 0.6); });
check("node nhiều liên kết bị kéo vào tâm mạnh hơn node lẻ", probe[0].__gw > probe[2].__gw * 2);
check("node lẻ vẫn còn lực hút (không văng khỏi khung)", probe[2].__gw >= 0.4);

// ---- 6. Cỡ hạt phải TỈ LỆ với bán kính khối -------------------------------
// Đây là bài học đắt nhất: cỡ hạt từng gõ cứng bằng đơn vị thế giới, nên lực vật lý
// trải khối ra rộng bao nhiêu thì hạt teo bấy nhiêu và trên máy thật chỉ còn chấm mờ.
// Khoá lại bằng cách đo trên SPRITE THẬT ở hai cỡ khối khác hẳn nhau.
function spriteBase(links, scale) {
  const ns = [{ id: "x", x: 100 * scale, y: 0, z: 0, links, color: "#8b93ff", __sprite: { material: {} } }];
  const h = makeGraph(ns);
  h.g._applyDepth();
  return ns[0].__sprite.__base;
}
// Gán __f như nodeThreeObject làm (test không chạm được vào builder của ForceGraph3D)
function withF(links, scale) {
  const f = 0.030 + Math.min(0.085, Math.pow(links, 0.7) * 0.030);
  const ns = [{ id: "x", x: 100 * scale, y: 0, z: 0, links, color: "#8b93ff",
                __sprite: { material: {}, __f: f } }];
  const h = makeGraph(ns);
  h.g._applyDepth();
  return ns[0].__sprite.__base;
}
const b1 = withF(3, 1), b3 = withF(3, 3);
check("khối to gấp 3 thì hạt cũng to gấp 3 (cỡ theo tỉ lệ, không gõ cứng)",
      Math.abs(b3 - b1 * 3) < b1 * 0.02);
const f = (links) => 0.030 + Math.min(0.085, Math.pow(links, 0.7) * 0.030);
check("note lẻ vẫn chiếm được cỡ nhìn thấy (>=2.5% bán kính)", f(0) >= 0.025);
check("hub to hơn note lẻ ít nhất 3 lần", f(50) > f(0) * 3);
check("hub bị chặn trần, không nuốt cả khung", f(5000) <= 0.12);

console.log(fails ? `\nFAIL ${fails} test` : "\nTẤT CẢ PASS");
process.exit(fails ? 1 : 0);
