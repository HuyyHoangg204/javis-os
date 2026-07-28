/* Chống tái phát: đang hover một node mà chuyển trang thì tooltip (position:fixed) phải
   tắt, kể cả khi canvas không bao giờ nhận được mouseleave / hover-null.
   Chạy: node dashboard/test_graph_tooltip_cleanup.js */
global.window = global;
global.document = {
  createElement: () => ({
    getContext: () => ({
      createRadialGradient: () => ({ addColorStop() {} }),
      fillRect() {},
    }),
  }),
};
global.window.dispatchEvent = () => {};

require("./graph.js");
require("./graph3d.js");

let fails = 0;
function check(name, condition) {
  console.log((condition ? "ok  " : "FAIL ") + name);
  if (!condition) fails++;
}

function graphStub() {
  return {
    pauseAnimation() {},
    controls() { return { autoRotate: true }; },
  };
}

const tooltip2d = { style: { display: "block" } };
const graph2d = new window.JavisGraph({}, tooltip2d);
graph2d.graph = graphStub();
graph2d.pause();
check("2D pause hides a hovered tooltip", tooltip2d.style.display === "none");

const tooltip3d = { style: { display: "block" } };
const graph3d = new window.JavisGraph3D({}, tooltip3d);
graph3d.graph = graphStub();
graph3d.pause();
check("3D pause hides a hovered tooltip", tooltip3d.style.display === "none");

// Overlapping navigation/settings events may pause an already paused renderer.
tooltip3d.style.display = "block";
graph3d.pause();
check("repeated 3D pause still clears stale tooltip", tooltip3d.style.display === "none");

if (fails) {
  console.log(`FAIL ${fails} test(s)`);
  process.exit(1);
}
console.log("ALL PASS");
