// ============================================
// JAVIS OS - 3D Graph (V.A.U.L.T. nebula HUD)
// Node = sprite phát sáng additive (glow) → khối cầu tinh vân như chase.h.ai.
// Dùng window.THREE global (load trước 3d-force-graph) + ForceGraph3D UMD.
// ============================================

// Hai bảng mực cho tinh vân 3D.
// TỐI: sprite cộng sáng (AdditiveBlending) - mật độ đọc thành độ sáng, đúng chất tinh vân.
// SÁNG: cộng sáng trên nền giấy cho ra TRẮNG BỆT (r+g+b dồn lên 255), cả khối não biến
// mất. Nên tông sáng chuyển sang chồng thường + mực sẫm, đọc như vệt màu nước trên giấy.
//
// KHÔNG CÒN LÕI TRẮNG trong hạt. Bản cũ để mỗi sprite một chấm trắng ở tâm; vài trăm
// sprite cộng sáng chồng nhau trong khối cầu đặc thì tổng dồn hết về trắng, màu danh mục
// biến mất sạch và cả quả cầu thành đám lốm đốm xám. Giữ đúng hue ngay từ tâm hạt rồi hạ
// alpha xuống thì chồng bao nhiêu lớp vẫn ra màu, chỉ sáng dần lên.
let G3 = {
  light: false,
  additive: true,
  fallback: "#b98cff",
  // ĐĨA ĐẶC viền mềm, không phải điểm-có-đuôi. Bản trước để đặc tới 9% bán kính rồi
  // tắt ngay; ở cỡ màn hình thật cái lõi đặc đó bé hơn 1 pixel nên chỉ còn quầng mờ -
  // ra đúng mấy đốm nhoè không đọc được. Đặc tới 34% thì hạt luôn là một CHẤM thật.
  glowStops: [[0, 1.0], [0.34, 0.96], [0.52, 0.45], [0.78, 0.10]],
  baseOpacity: 0.95,
  // Dây nối phải MỜ HƠN note. Bản trước để dây 0.2 còn note 0.52 nên nhìn ra mạng
  // nhện xám, còn note thì mất tăm - ngược hẳn thứ tự quan trọng.
  link: "rgba(150,140,225,0.9)",
  linkOpacity: 0.11,

  // Sương mù theo chiều sâu: hạt xa mờ dần về màu nền → khối có thể tích thay vì dẹt.
  // fogK là hệ số chia theo bán kính đo được (xem _applyDepth), không phải hằng số tuyệt
  // đối - brain to nhỏ khác nhau nên sương phải co giãn theo.
  fog: 0x05050c, fogK: 0.13,

  // Lõi = một ĐỐM THAN ẤM nhỏ, không phải đèn pha. Bản trước để coreScale 1.25 (đường
  // kính 2.5 lần bán kính khối) nên nó phủ trùm toàn bộ đồ thị thành đám sương tím và
  // nuốt sạch node. 0.38 giữ nó gọn trong lòng khối, đọc ra "tim" chứ không phải "mù".
  // Màu đi từ cam thương hiệu ra tím - hơi ấm của Javis nằm ở đây.
  core: [[0, "rgba(255,216,172,0.90)"], [0.16, "rgba(255,146,74,0.43)"],
         [0.42, "rgba(155,92,224,0.17)"], [1, "rgba(72,46,152,0)"]],
  coreScale: 0.38,

  // Bụi vành thưa và mờ: starfield phía sau đã lo phần hạt nền rồi, lớp này chỉ thêm
  // thị sai cho có khối. Dày quá là thành lớp sương thứ ba, đúng lỗi vừa mắc.
  dust: 0xbdaced, dustOpacity: 0.28, dustSize: 1.4, dustCount: 260,

  particle: [                                     // hạt chạy dọc dây lúc đang nghĩ
    [0, "rgba(255,255,255,1)"], [0.06, "rgba(255,210,120,0.95)"],
    [0.18, "rgba(255,140,40,0.75)"], [0.40, "rgba(255,90,10,0.30)"],
    [0.70, "rgba(200,60,0,0.08)"], [1, "rgba(180,40,0,0)"],
  ],
  particleColor: "rgba(255,165,50,0.95)",
  particleOpacity: 0.8,
};
const G3_DARK = G3;
const G3_LIGHT = {
  light: true,
  additive: false,
  fallback: "#7340c9",
  glowStops: [[0, 1.0], [0.34, 0.96], [0.52, 0.45], [0.78, 0.10]],
  // Trên giấy mực phải ĐẶC mới ra chấm sắc nét; để mờ là chìm nghỉm vào nền ngà.
  baseOpacity: 1.0,
  // Dây mảnh màu sẫm trên giấy cần đậm hơn hẳn mức của nền đen mới thấy.
  link: "rgba(92,74,140,0.9)",
  linkOpacity: 0.16,

  fog: 0xf1eae0, fogK: 0.10,

  // Trên giấy KHÔNG có "nguồn sáng" - lõi thành vệt ửng đào-lavender rất nhạt và NHỎ,
  // đọc như chỗ mực thấm đậm nhất giữa trang. Đậm hơn nữa là cả trang thành màn sữa.
  core: [[0, "rgba(255,196,150,0.30)"], [0.20, "rgba(214,140,90,0.15)"],
         [0.50, "rgba(150,110,220,0.07)"], [1, "rgba(255,255,255,0)"]],
  coreScale: 0.36,

  dust: 0x7d7398, dustOpacity: 0.22, dustSize: 1.3, dustCount: 260,

  particle: [
    [0, "rgba(150,44,0,0.98)"], [0.16, "rgba(200,70,10,0.85)"],
    [0.38, "rgba(232,93,31,0.42)"], [0.68, "rgba(232,120,60,0.12)"],
    [1, "rgba(232,140,80,0)"],
  ],
  particleColor: "rgba(190,64,8,0.95)",
  particleOpacity: 0.9,
};

// Cỡ hạt tính theo TỈ LỆ bán kính khối: note lẻ 0.030R, hub tối đa 0.115R.
const NODE_F0 = 0.030, NODE_FK = 0.030, NODE_FMAX = 0.085;

const _texCache = {};
function glowTexture(THREE, hex) {
  const key = hex + (G3.light ? "|L" : "|D");
  if (_texCache[key]) return _texCache[key];
  const s = 96;
  const cv = document.createElement("canvas");
  cv.width = cv.height = s;
  const ctx = cv.getContext("2d");
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  // Toàn bộ dải là MỘT hue - không chen màu trắng vào tâm (xem ghi chú ở bảng G3).
  G3.glowStops.forEach(([at, a]) => g.addColorStop(at, hexA(hex, a)));
  g.addColorStop(1, hexA(hex, 0));               // viền tan vào nền
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(cv);
  _texCache[key] = tex;
  return tex;
}

// Lõi sáng ở tâm tinh vân. Vẽ to (256px) vì nó được phóng lên cỡ cả khối não.
function coreTexture(THREE) {
  const key = "__core" + (G3.light ? "|L" : "|D");
  if (_texCache[key]) return _texCache[key];
  const s = 256;
  const cv = document.createElement("canvas");
  cv.width = cv.height = s;
  const ctx = cv.getContext("2d");
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  G3.core.forEach(([at, c]) => g.addColorStop(at, c));
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(cv);
  _texCache[key] = tex;
  return tex;
}

function particleGlowTexture(THREE) {
  const key = "__particle" + (G3.light ? "|L" : "|D");
  if (_texCache[key]) return _texCache[key];
  const s = 128;
  const cv = document.createElement("canvas");
  cv.width = cv.height = s;
  const ctx = cv.getContext("2d");
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  G3.particle.forEach(([at, c]) => g.addColorStop(at, c));
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(cv);
  _texCache[key] = tex;
  return tex;
}
function hexA(hex, a) {
  const m = hex.replace("#", "");
  const r = parseInt(m.substring(0, 2), 16);
  const g = parseInt(m.substring(2, 4), 16);
  const b = parseInt(m.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

// Đồng bộ bảng mực với tông đang bật. Gọi ở đầu _recolor() và trong load() thay vì
// đăng ký listener riêng: graph.js nạp TRƯỚC file này nên listener của nó chạy trước,
// và nó gọi thẳng __javisGraph._recolor() - nếu G3 chờ listener của mình thì lúc đó
// vẫn còn là bảng cũ. Tự đọc tông ngay tại chỗ dùng là hết phụ thuộc thứ tự.
function _syncG3() {
  const light = typeof document !== "undefined" && document.documentElement
    ? document.documentElement.getAttribute("data-theme") === "light"
    : false;
  G3 = light ? G3_LIGHT : G3_DARK;
}

// Lực hút về tâm 3D (x,y,z) → cả tinh vân co tròn lại, node lẻ/cụm xa bị kéo vào gần.
// Sức hút TỈ LỆ THEO SỐ LIÊN KẾT: note nhiều liên kết bị kéo vào tâm mạnh hơn, note lẻ
// trôi ra vành. Nhờ đó khối có lõi đặc rồi loãng dần ra rìa thay vì là quả cầu đều tăm
// tắp - vừa đẹp hơn vừa mang nghĩa: cái gì quan trọng thì nằm giữa.
function centerGravity3D(strength) {
  let _nodes = [];
  const force = (alpha) => {
    const k = strength * alpha;
    for (let i = 0; i < _nodes.length; i++) {
      const n = _nodes[i];
      const w = n.__gw || 1;
      n.vx -= n.x * k * w; n.vy -= n.y * k * w; n.vz -= (n.z || 0) * k * w;
    }
  };
  force.initialize = (ns) => {
    _nodes = ns || [];
    let max = 1;
    for (const n of _nodes) max = Math.max(max, n.links || 0);
    // Mũ 0.6 để hub không hút quá gắt: chênh lệch liên kết thường rất lệch (vài hub
    // trăm link, phần lớn 0-2), lấy tuyến tính là hub dính chặt thành một cục ở tâm.
    for (const n of _nodes) n.__gw = 0.45 + 1.35 * Math.pow((n.links || 0) / max, 0.6);
  };
  return force;
}

class JavisGraph3D {
  constructor(container, tooltip) {
    this.container = container;
    this.tooltip = tooltip;
    this.graph = null;
    this.level = 0;
    this._smooth = 0;
    this._raf = null;
    this._sprites = [];
    this._thinking = false;
    this._firingNodes = new Map();
    this._births = new Map();   // sprite -> frames còn lại của hiệu ứng "nảy sinh"
    this._paused = false;
    this._fitTimer = null;
    // Expose để Console (console.js) gọi pause()/wake() khi chuyển trang - không cần sửa app.js.
    window.__javisGraph = this;
    window.dispatchEvent(new Event("javis-graph-created"));
  }

  async load(query = "source=all") {
    _syncG3();   // vào 3D sau khi đã đổi tông ở 2D → bắt kịp bảng mực trước khi dựng sprite
    const res = await fetch(`/graph?${query}`);
    const data = await res.json();
    if (window.JavisCatColorize) window.JavisCatColorize(data.nodes);   // tô màu theo danh mục như 2D
    const links = data.edges.map(e => ({ source: e.source, target: e.target }));
    const THREE = window.THREE;

    if (!this.graph) {
      if (!window.ForceGraph3D) throw new Error("Thư viện 3D chưa tải (kiểm tra mạng)");
      if (!THREE) throw new Error("THREE chưa tải");

      this.graph = ForceGraph3D()(this.container)
        .backgroundColor("rgba(0,0,0,0)")
        .showNavInfo(false)
        .onEngineStop(() => {
          this._settled = true;
          // 3D ForceGraph giữ camera khởi tạo khá gần. Trên desktop khối node tự co
          // nên nhìn như đã fit, nhưng viewport mobile thấp vẫn giữ trạng thái phóng to.
          // Chỉ canh lại camera mobile sau khi physics đã lắng để không thay đổi desktop.
          this._scheduleMobileFit(60);
        })
        .nodeThreeObject(n => {
          const mat = new THREE.SpriteMaterial({
            map: glowTexture(THREE, n.color || G3.fallback),
            blending: G3.additive ? THREE.AdditiveBlending : THREE.NormalBlending,
            depthWrite: false,
            transparent: true,
            fog: true,            // chịu sương mù → hạt ở xa mờ đi, khối có chiều sâu
          });
          const sp = new THREE.Sprite(mat);
          // Cỡ hạt là TỈ LỆ của bán kính khối, không phải số tuyệt đối. Bản trước gõ
          // cứng 3.2..20 đơn vị thế giới; lực vật lý trải khối ra rộng bao nhiêu thì hạt
          // teo tương ứng bấy nhiêu, nên trên máy thật chỉ còn mấy chấm mờ. Nhân theo
          // bán kính thì khối to nhỏ thế nào hạt cũng giữ đúng tỉ lệ nhìn thấy được.
          // Bán kính thật đo được sau khi physics lắng - _applyDepth sẽ chỉnh lại.
          const f = NODE_F0 + Math.min(NODE_FMAX, Math.pow(n.links || 0, 0.7) * NODE_FK);
          sp.__f = f;
          sp.__base = (this._R || 80) * f;
          sp.scale.set(sp.__base, sp.__base, 1);
          n.__sprite = sp;
          return sp;
        })
        .nodeThreeObjectExtend(false)
        .linkColor(() => G3.link)
        .linkWidth(0)
        .linkOpacity(G3.linkOpacity)
        .linkDirectionalParticles(0)
        .linkDirectionalParticleWidth(4)
        .linkDirectionalParticleColor(() => G3.particleColor)
        .linkDirectionalParticleSpeed(0.007)
        .onNodeHover(n => {
          this.container.style.cursor = n ? "pointer" : "grab";
          if (n && this.tooltip) {
            this.tooltip.style.display = "block";
            this.tooltip.innerHTML = `<strong>${n.label}</strong><br><span class="tt-path">${n.path}</span><br><span class="tt-links">${n.links} kết nối · click để mở</span>`;
          } else if (this.tooltip) {
            this.tooltip.style.display = "none";
          }
        })
        .onNodeClick(n => {
          const dist = 90;
          const r = 1 + dist / Math.hypot(n.x || 1, n.y || 1, n.z || 1);
          this.graph.cameraPosition({ x: (n.x || 0) * r, y: (n.y || 0) * r, z: (n.z || 0) * r }, n, 800);
          if (window.onGraphNodeClick) window.onGraphNodeClick(n);
        });

      // Layout cầu chặt: lực đẩy vừa, link ngắn, + hút về tâm cho co TRÒN lại (kéo cụm/node xa vào)
      this.graph.d3Force("charge").strength(-45);
      const linkForce = this.graph.d3Force("link");
      if (linkForce) linkForce.distance(28);
      this.graph.d3Force("gravity", centerGravity3D(0.06));

      // Sương đặt NGAY tại đây, trước lần graphData() đầu tiên (là lúc sprite node được
      // dựng và shader biên dịch). Xem ghi chú ở _ensureFog.
      this._ensureFog();

      const controls = this.graph.controls();
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.6;   // quay nhẹ liên tục - luôn "sống"

      this._animate();
    }

    this._settled = false;
    if (this._fitTimer) clearTimeout(this._fitTimer);
    this._slowFrame = 0;
    this.graph.graphData({ nodes: data.nodes, links });
    this._buildCore();
    this._buildDust();
    // Gom sprite refs + dựng adjacency (để lan truyền firing theo synapse).
    // _applyDepth phải chạy SAU khi physics đã đẩy node ra khỏi gốc, không thì bán kính
    // đo được bằng 0 và sương dày vô hạn. Đo lại lần nữa lúc lắng cho khớp cỡ thật.
    setTimeout(() => { this._rebuildRefs(); this._applyDepth(); }, 200);
    setTimeout(() => this._applyDepth(), 2200);
    this.resize();
    return data;
  }

  // ---- Lõi sáng + bụi vành + sương mù ----------------------------------------
  // Ba lớp này quyết định phần lớn "chất" của tinh vân, và đều phải dựng lại khi đổi tông.

  _scene() {
    return this.graph && this.graph.scene ? this.graph.scene() : null;
  }

  // Bán kính đặc trưng của khối = khoảng cách trung bình từ tâm tới node. Mọi thứ khác
  // (cỡ lõi, cỡ vỏ bụi, độ dày sương) đều suy ra từ số này nên brain to nhỏ đều hợp cỡ.
  _radius() {
    const ns = (this.graph && this.graph.graphData().nodes) || [];
    let sum = 0, k = 0;
    for (const n of ns) {
      if (n.x == null) continue;
      sum += Math.hypot(n.x, n.y, n.z || 0); k++;
    }
    return k ? Math.max(30, sum / k) : 80;
  }

  _buildCore() {
    const THREE = window.THREE, scene = this._scene();
    if (!THREE || !scene) return;
    this._disposeCore();
    const mat = new THREE.SpriteMaterial({
      map: coreTexture(THREE),
      blending: G3.additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      depthWrite: false,
      transparent: true,
      fog: false,       // lõi LÀ nguồn sáng, không để sương ăn mất nó
    });
    const sp = new THREE.Sprite(mat);
    sp.renderOrder = -1;             // vẽ trước node để node nổi lên trên nền lõi
    scene.add(sp);
    this._core = sp;
  }

  _buildDust() {
    const THREE = window.THREE, scene = this._scene();
    if (!THREE || !scene) return;
    this._disposeDust();
    const N = G3.dustCount || 320;
    const pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      // Điểm đều trên mặt cầu (u phân bố đều mới không dồn về hai cực), bán kính lệch
      // ngẫu nhiên trong [0.95, 2.15] để thành lớp vỏ dày chứ không phải vòng mỏng.
      const u = Math.random() * 2 - 1;
      const th = Math.random() * Math.PI * 2;
      const sq = Math.sqrt(1 - u * u);
      const rr = 0.95 + Math.pow(Math.random(), 0.7) * 1.2;
      pos[i * 3] = sq * Math.cos(th) * rr;
      pos[i * 3 + 1] = sq * Math.sin(th) * rr;
      pos[i * 3 + 2] = u * rr;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const mat = new THREE.PointsMaterial({
      color: G3.dust, size: G3.dustSize, sizeAttenuation: true,
      transparent: true, opacity: G3.dustOpacity, depthWrite: false,
      blending: G3.additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      fog: true,
    });
    const pts = new THREE.Points(geo, mat);
    pts.renderOrder = -2;
    scene.add(pts);
    this._dust = pts;
  }

  // Sương phải TỒN TẠI TRƯỚC khi bất kỳ material nào được biên dịch. three.js nướng
  // việc "có dùng sương hay không" vào shader lúc dựng chương trình; gán scene.fog sau
  // khi sprite đã tạo thì shader cũ không có đoạn sương, và sương coi như vô hiệu (trừ
  // khi ép needsUpdate cho từng material - tốn hơn và dễ sót). Nên tạo ngay lúc dựng
  // graph, về sau chỉ sửa .color/.density (đều là uniform, không phải biên dịch lại).
  _ensureFog() {
    const THREE = window.THREE, scene = this._scene();
    if (!THREE || !scene || scene.fog) return;
    scene.fog = new THREE.FogExp2(G3.fog, G3.fogK / 80);
  }

  // Cỡ lõi/bụi + độ dày sương theo bán kính thật. Gọi lại khi dữ liệu hoặc tông đổi.
  _applyDepth() {
    const scene = this._scene();
    if (!scene) return;
    this._ensureFog();
    const R = this._radius();
    this._R = R;
    if (scene.fog) {
      // FogExp2: độ mờ = 1 - exp(-(density*depth)^2). Camera thường cách tâm ~2.5R nên
      // node trải từ ~1.5R tới ~3.5R; density = fogK/R cho mặt gần mờ nhẹ, mặt xa mờ rõ.
      scene.fog.density = G3.fogK / R;
      if (scene.fog.color && scene.fog.color.setHex) scene.fog.color.setHex(G3.fog);
    }
    if (this._dust) this._dust.scale.setScalar(R);
    this._coreR = R * G3.coreScale * 2;
    // Sprite dựng lúc chưa biết bán kính thật nên phải chỉnh lại cỡ tại đây.
    // Vòng vẽ đọc sp.__base nên chỉ cần cập nhật nó, không đụng scale trực tiếp.
    for (const n of (this.graph.graphData().nodes || [])) {
      const sp = n.__sprite;
      if (sp && sp.__f) sp.__base = R * sp.__f;
    }
  }

  _disposeCore() {
    if (!this._core) return;
    const scene = this._scene();
    if (scene) scene.remove(this._core);
    if (this._core.material) this._core.material.dispose();
    this._core = null;
  }

  _disposeDust() {
    if (!this._dust) return;
    const scene = this._scene();
    if (scene) scene.remove(this._dust);
    if (this._dust.geometry) this._dust.geometry.dispose();
    if (this._dust.material) this._dust.material.dispose();
    this._dust = null;
  }

  // Gom lại sprite refs + adjacency từ graphData hiện tại (gọi sau mỗi lần đổi data)
  _rebuildRefs() {
    if (!this.graph) return;
    const nodes = this.graph.graphData().nodes;
    this._sprites = nodes.filter(n => n.__sprite).map(n => n.__sprite);
    const idToIdx = {};
    let k = 0;
    nodes.forEach(n => { if (n.__sprite) { idToIdx[n.id] = k; k++; } });
    this._adj = this._sprites.map(() => []);
    this.graph.graphData().links.forEach(l => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      const si = idToIdx[s], ti = idToIdx[t];
      if (si != null && ti != null) { this._adj[si].push(ti); this._adj[ti].push(si); }
    });
  }

  nodeStats() {
    if (!this.graph) return { nodes: 0, links: 0 };
    const d = this.graph.graphData();
    return { nodes: d.nodes.length, links: d.links.length };
  }

  // Đổi tông. Sprite của three.js đã dựng xong không tự đổi theo bảng màu, nên phải
  // thay TẬN NƠI: gán texture mới + đổi kiểu chồng lớp (cộng sáng ↔ chồng thường) cho
  // từng material đang sống. Bỏ qua bước này thì tông sáng chỉ thấy một khối trắng bệt.
  // Vẫn giữ nguyên graphData nên camera, góc quay và vị trí node không bị đặt lại.
  _recolor() {
    const THREE = window.THREE;
    _syncG3();
    if (!this.graph || !THREE) return;
    const blending = G3.additive ? THREE.AdditiveBlending : THREE.NormalBlending;
    const at = window.JavisCatColorAt;

    (this.graph.graphData().nodes || []).forEach(n => {
      if (at && n.__catIdx != null) n.color = at(n.__catIdx);
      const sp = n.__sprite;
      if (!sp || !sp.material) return;
      sp.material.map = glowTexture(THREE, n.color || G3.fallback);
      sp.material.blending = blending;
      sp.material.needsUpdate = true;
    });

    // Hạt "đang nghĩ" đang bay: đổi texture + kiểu chồng lớp tại chỗ cho khỏi dựng lại.
    (this._thinkSprites || []).forEach(({ sp }) => {
      if (!sp || !sp.material) return;
      sp.material.map = particleGlowTexture(THREE);
      sp.material.blending = blending;
      sp.material.opacity = G3.particleOpacity;
      sp.material.needsUpdate = true;
    });

    try {
      this.graph.linkColor(() => G3.link)
        .linkOpacity(G3.linkOpacity)
        .linkDirectionalParticleColor(() => G3.particleColor);
    } catch (e) {}

    // Lõi, bụi và sương đều mang màu của tông nên phải dựng lại hẳn, không chỉ đổi map.
    this._buildCore();
    this._buildDust();
    this._applyDepth();
  }

  // Thêm/cập nhật 1 node realtime (brain vừa sinh ra hoặc sửa note).
  // linkTargets = stem (lowercase) các wikilink trong note đó.
  addOrUpdate(node, linkTargets, isNew) {
    if (!this.graph || !node || !node.id) return { created: false };
    const data = this.graph.graphData();
    const byId = new Map(data.nodes.map(n => [n.id, n]));
    let target = byId.get(node.id);
    let created = false;

    if (!target) {
      // Mọc ra cạnh 1 node hàng xóm đã có (nếu link tới) → trông như nảy từ mạng
      let px = 0, py = 0, pz = 0;
      const nb = (linkTargets || []).map(s => byId.get(s)).find(Boolean);
      if (nb) { px = (nb.x || 0) + (Math.random() - 0.5) * 10; py = (nb.y || 0) + (Math.random() - 0.5) * 10; pz = (nb.z || 0) + (Math.random() - 0.5) * 10; }
      target = Object.assign({}, node, { x: px, y: py, z: pz, links: 0 });
      data.nodes.push(target);
      byId.set(target.id, target);
      created = true;
    } else {
      if (node.color) target.color = node.color;
      if (node.path) target.path = node.path;
    }

    // Chuẩn hoá link về dạng id-string + tập key để khử trùng
    const keyOf = (a, b) => (a < b ? a + "|" + b : b + "|" + a);
    const links = data.links.map(l => ({
      source: typeof l.source === "object" ? l.source.id : l.source,
      target: typeof l.target === "object" ? l.target.id : l.target,
    }));
    const seen = new Set(links.map(l => keyOf(l.source, l.target)));

    (linkTargets || []).forEach(stem => {
      const tgt = byId.get(stem);
      if (!tgt || tgt.id === target.id) return;
      const k = keyOf(target.id, tgt.id);
      if (seen.has(k)) return;
      seen.add(k);
      links.push({ source: target.id, target: tgt.id });
      target.links = (target.links || 0) + 1;
      tgt.links = (tgt.links || 0) + 1;
    });

    this.graph.graphData({ nodes: data.nodes, links });
    // Sau khi sprite của node mới dựng xong → rebuild refs + bật hiệu ứng nảy sinh
    setTimeout(() => {
      this._rebuildRefs();
      if (created && target.__sprite) this._births.set(target.__sprite, 36);
    }, 60);

    return { created };
  }

  setLevel(l) { this.level = l; }

  setThinking(active) {
    this._thinking = active;
    if (!this.graph) return;
    if (active) {
      this._buildThinkingSprites();
    } else {
      this._clearThinkingSprites();
      this._firingNodes.clear();
    }
  }

  _buildThinkingSprites() {
    this._clearThinkingSprites();
    const THREE = window.THREE;
    if (!THREE || !this.graph) return;
    const scene = this.graph.scene && this.graph.scene();
    if (!scene) return;
    const links = this.graph.graphData().links;
    if (!links || !links.length) return;
    // Lấy tối đa 60 link ngẫu nhiên để không quá nặng
    const pool = links.length > 100 ? links.filter(() => Math.random() < 100 / links.length) : links;
    this._thinkSprites = [];
    pool.forEach(link => {
      const count = 2 + (Math.random() < 0.5 ? 1 : 0);
      for (let i = 0; i < count; i++) {
        const mat = new THREE.SpriteMaterial({
          map: particleGlowTexture(THREE),
          blending: G3.additive ? THREE.AdditiveBlending : THREE.NormalBlending,
          depthWrite: false,
          transparent: true,
          opacity: G3.particleOpacity,
        });
        const sp = new THREE.Sprite(mat);
        const size = 3.5 + Math.random() * 3;
        sp.scale.set(size, size, 1);
        scene.add(sp);
        this._thinkSprites.push({ sp, link, t: Math.random(), speed: 0.007 + Math.random() * 0.008 });
      }
    });
  }

  _clearThinkingSprites() {
    if (!this._thinkSprites || !this._thinkSprites.length) return;
    const scene = this.graph && this.graph.scene && this.graph.scene();
    this._thinkSprites.forEach(({ sp }) => {
      if (scene) scene.remove(sp);
      if (sp.material) sp.material.dispose();
    });
    this._thinkSprites = [];
  }

  _animate() {
    const tick = () => {
      if (this._paused) { this._raf = null; return; }   // pause: dừng hẳn vòng lặp (kể cả khi load() vừa gọi lại)
      this._raf = requestAnimationFrame(tick);
      if (!this.graph) return;
      // Không render khi tab ẩn - tiết kiệm CPU/GPU hoàn toàn
      if (document.hidden) return;
      // Sau khi physics settle: giảm còn ~15fps (bỏ qua 3/4 frame)
      if (this._settled) {
        this._slowFrame = (this._slowFrame || 0) + 1;
        if (this._slowFrame % 4 !== 0) return;
      }
      const t = this.level || 0;
      if (t > this._smooth) this._smooth += (t - this._smooth) * 0.5;
      else this._smooth += (t - this._smooth) * 0.12;
      const lvl = this._smooth;

      // Pulse từng sprite: phồng + sáng theo nhịp giọng
      const pulse = 1 + lvl * 1.6;
      // Nền dịu, chừa khoảng trống cho node "suy nghĩ" loé lên nổi bật hẳn lên.
      const op = Math.min(1, G3.baseOpacity + lvl * 0.5);
      for (const sp of this._sprites) {
        if (!sp) continue;
        const b = sp.__base;
        sp.scale.set(b * pulse, b * pulse, 1);
        if (sp.material) sp.material.opacity = op;
      }

      // --- BIRTH: node vừa sinh ra → loé sáng to rồi co về kích thước thật ---
      if (this._births.size) {
        for (const [sp, fr] of this._births) {
          if (!sp) { this._births.delete(sp); continue; }
          const t = fr / 36;                       // 1 → 0
          const grow = 1 + t * 3.2;                // bắt đầu to (pop) → settle
          const b = sp.__base || 5;
          sp.scale.set(b * grow, b * grow, 1);
          if (sp.material) sp.material.opacity = Math.min(1, 0.5 + (1 - t) * 0.6 + t * 0.4);
          const next = fr - 1;
          if (next <= 0) this._births.delete(sp);
          else this._births.set(sp, next);
        }
      }

      // Quay tròn nhẹ liên tục - tự xoay scene
      const scene = this.graph.scene && this.graph.scene();
      if (scene) scene.rotation.y += 0.0018 + lvl * 0.012;

      // Lõi thở theo giọng nói. Sprite luôn quay mặt về camera nên nó là quầng sáng
      // phẳng ở tâm, đúng ý: một nguồn sáng chứ không phải một quả cầu đặc.
      if (this._core) {
        const R = (this._coreR || 100) * (1 + lvl * 0.22);
        this._core.scale.set(R, R, 1);
        if (this._core.material) this._core.material.opacity = 0.85 + lvl * 0.15;
      }
      // Bụi vành trôi NGƯỢC chiều scene rất chậm → sinh thị sai, mắt đọc ra khối 3D
      // thay vì một tấm ảnh phẳng đang quay.
      if (this._dust) {
        this._dust.rotation.y -= 0.0006;
        this._dust.rotation.x += 0.00018;
      }

      this._frame = (this._frame || 0) + 1;

      // --- THINKING PARTICLES: đốm sáng bay dọc link ---
      if (this._thinking && this._thinkSprites && this._thinkSprites.length) {
        for (const p of this._thinkSprites) {
          p.t = (p.t + p.speed) % 1;
          const src = p.link.source;
          const tgt = p.link.target;
          if (!src || !tgt || src.x == null) continue;
          p.sp.position.set(
            src.x + (tgt.x - src.x) * p.t,
            src.y + (tgt.y - src.y) * p.t,
            src.z + (tgt.z - src.z) * p.t,
          );
          // Fade in từ nguồn, fade out gần đích - trông như bong bóng sáng trôi
          p.sp.material.opacity = Math.sin(p.t * Math.PI) * 0.85 + 0.1;
        }
      }

      // --- THINKING: nơron kích hoạt + LAN TRUYỀN theo synapse ---
      if (this._thinking) {
        const n = this._sprites.length;
        // Điểm khởi phát: 1-2 node "loé" lên thưa thớt (ý nghĩ mới) - chậm cho đỡ rối
        if (n > 0 && this._frame % 14 === 0) {
          const seeds = Math.max(2, Math.floor(n * 0.02));
          for (let i = 0; i < seeds; i++) {
            this._firingNodes.set(Math.floor(Math.random() * n), 14);
          }
        }
        // Lan truyền chậm: node cháy mạnh kích hoạt hàng xóm → sóng dịu chạy qua mạng
        if (this._adj && this._frame % 4 === 0) {
          const toAdd = [];
          for (const [idx, frames] of this._firingNodes) {
            if (frames >= 9) {
              const nb = this._adj[idx];
              if (nb) for (const j of nb) {
                if (!this._firingNodes.has(j) && Math.random() < 0.06) toAdd.push(j);
              }
            }
          }
          for (const j of toAdd) this._firingNodes.set(j, 12);
        }
        // Animate firing nodes - sáng lên rồi tắt dần
        for (const [idx, frames] of this._firingNodes) {
          const sp = this._sprites[idx];
          if (sp) {
            const t = Math.min(1, frames / 14);
            const s = sp.__base * (pulse + t * 2.0);   // phồng dịu hơn
            sp.scale.set(s, s, 1);
            if (sp.material) sp.material.opacity = Math.min(1, 0.6 + t * 0.5);
          }
          const next = frames - 1;
          if (next <= 0) this._firingNodes.delete(idx);
          else this._firingNodes.set(idx, next);
        }
      }
    };
    tick();
  }

  resize() {
    if (this.graph) {
      this.graph.width(this.container.clientWidth);
      this.graph.height(this.container.clientHeight);
      // Safari/Chrome mobile có thể đổi chiều cao visual viewport sau khi thanh địa chỉ
      // co lại. Fit lại trên kích thước cuối, nhưng chỉ khi layout node đã ổn định.
      if (this._settled) this._scheduleMobileFit(140);
    }
  }

  _isMobileViewport() {
    return !!(window.matchMedia && window.matchMedia("(max-width: 860px)").matches);
  }

  _scheduleMobileFit(delay) {
    if (!this.graph || !this._isMobileViewport()) return;
    if (this._fitTimer) clearTimeout(this._fitTimer);
    this._fitTimer = setTimeout(() => {
      this._fitTimer = null;
      if (!this.graph || !this._settled || !this._isMobileViewport()) return;
      try {
        // Padding nhỏ vì người dùng có thể ẩn toàn bộ HUD để ngắm brain trọn khung.
        this.graph.zoomToFit(650, 24);
      } catch (e) {}
    }, delay == null ? 0 : delay);
  }

  stop() { if (this._raf) cancelAnimationFrame(this._raf); this._raf = null; }
  resume() { if (!this._raf) this._animate(); }

  // Pause SÂU - dùng khi rời cockpit (mở Console): dừng vòng render + engine vật lý +
  // autorotate → CPU/GPU về ~0, nhưng giữ context để bật lại tức thì. Đảo bằng wake().
  hideTooltip() {
    if (this.tooltip) this.tooltip.style.display = "none";
  }

  pause() {
    // Tooltip nằm NGOÀI canvas nên canvas bị che/đổi trang là không còn sự kiện rời
    // hover để tự ẩn. Chuyển trang nhanh cũng nuốt luôn sự kiện đó.
    this.hideTooltip();
    if (this._paused) return;
    this._paused = true;
    this.stop();                                  // dừng RAF render glow/firing
    if (this.graph) {
      try { this.graph.pauseAnimation(); } catch (e) {}   // dừng vòng render của force-graph
      try { const c = this.graph.controls(); if (c) c.autoRotate = false; } catch (e) {}
    }
  }
  wake() {
    if (!this._paused) return;
    this._paused = false;
    if (this.graph) {
      try { this.graph.resumeAnimation(); } catch (e) {}
      try { const c = this.graph.controls(); if (c) c.autoRotate = true; } catch (e) {}
      this.resize();                              // khung có thể đã đổi kích thước khi ẩn
    }
    this.resume();                                // chạy lại RAF
  }
  isPaused() { return !!this._paused; }
}

window.JavisGraph3D = JavisGraph3D;
window.dispatchEvent(new Event("javis-graph3d-ready"));
