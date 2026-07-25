"""Engine cho VIỆC NỀN (loop, việc Kanban, nhắc hẹn, tự học, tiêu hoá nguồn).

Trước đây việc nền luôn chạy bằng Claude Code, ô chọn ở trang Model bị khoá cứng vào
danh sách model của provider 'anthropic-cli' - muốn đẩy việc nền sang gói ChatGPT hay
một API rẻ để đỡ hạn mức Claude thì không có đường. Module này mở đường đó.

Cách nối vào (cố ý ít xâm lấn): các nơi chạy nền VẪN dựng engine Claude y như cũ, kèm
đủ allowlist/mode/MCP mà chúng vốn tính toán; xong xuôi mới gọi `swap()`. Nếu người dùng
để mặc định Claude thì `swap()` trả lại đúng engine đó, không đổi gì. Chọn provider khác
thì `swap()` đọc chính các thuộc tính engine Claude đã tính (system_prompt, cwd, vault,
mode, allowlist) và dựng engine tương ứng - nên mọi quyết định an toàn ở đầu kia được
thừa hưởng nguyên vẹn, không phải chép lại.

Ba loại engine, khác nhau ở CÔNG CỤ có được - đây là chỗ phải cẩn thận:
- anthropic-cli: Claude Code. Tool file native + Bash + MCP, chặn theo allowlist per-call.
- openai-oauth: Codex CLI, cũng là agent thật (đọc/ghi file + MCP qua profile javis).
  Sandbox của Codex ánh xạ theo mode: suggest -> read-only, auto -> workspace-write,
  full -> toàn quyền. KHÔNG có allowlist per-call như Claude nên chỉ chặn ở tầng sandbox.
- api (openrouter/openai/gemini/anthropic-api): KHÔNG có tool native. Bù lại hub cấp
  javis_read_file / javis_list_dir / javis_write_file / javis_use_skill + tool MCP, và
  javis_write_file tự chặn khi mode là suggest (mcp_hub._builtin_tools). Không có Bash,
  không có WebFetch - hẹp hơn Claude, nhưng đủ cho việc nền đọc/ghi ghi chú trong vault.

Hợp đồng sự kiện giữ y như ClaudeSDK để nơi gọi không phải sửa: query() sinh dict
{"type": "tool_call"|"final"|"error"|"usage", ...}. Đường API sinh "text" nhiều mảnh nên
ở đây gom lại thành đúng MỘT "final" ở cuối - việc nền đều chỉ đọc sự kiện final.
"""
from __future__ import annotations

import sys
from typing import Optional

import config as cfgmod

CLAUDE = "anthropic-cli"
CODEX = "openai-oauth"
API_PROVIDERS = ("openrouter", "openai", "gemini", "anthropic-api")

# provider -> tên trường chứa API key trong settings["model"]
_KEY_FIELD = {
    "openrouter": "openrouter_key",
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "anthropic-api": "anthropic_api_key",
}

# mode của Javis -> sandbox của Codex CLI
_CODEX_SANDBOX = {"suggest": "read-only", "auto": "workspace-write", "full": None}


def read_spec(settings: dict = None) -> dict:
    """{'provider','model'} của model việc nền. Cấu hình cũ chỉ có 'model' (luôn là alias
    Claude) nên thiếu provider = anthropic-cli - giữ nguyên hành vi bản cũ."""
    s = settings if settings is not None else cfgmod.read_settings()
    aux = (s.get("model", {}) or {}).get("auxiliary") or {}
    return {"provider": (aux.get("provider") or CLAUDE), "model": (aux.get("model") or "")}


def is_claude(spec: dict) -> bool:
    return (spec or {}).get("provider", CLAUDE) == CLAUDE


def api_key_for(provider: str, settings: dict = None) -> str:
    field = _KEY_FIELD.get(provider)
    if not field:
        return ""
    s = settings if settings is not None else cfgmod.read_settings()
    return (s.get("model", {}) or {}).get(field) or ""


def availability(spec: dict, settings: dict = None) -> tuple:
    """(dùng được?, lý do nếu không). Để trang Model cảnh báo TRƯỚC khi người dùng chọn
    nhầm một provider chưa đăng nhập / chưa có key rồi việc nền chết lặng lẽ."""
    prov = (spec or {}).get("provider", CLAUDE)
    if prov == CLAUDE:
        return True, ""
    if prov == CODEX:
        try:
            from claude_cli import find_codex_cli
            if not find_codex_cli():
                return False, "Chưa cài Codex CLI (cần đăng nhập gói ChatGPT)."
        except Exception:
            return False, "Không kiểm tra được Codex CLI."
        return True, ""
    if prov in API_PROVIDERS:
        if not api_key_for(prov, settings):
            return False, f"Chưa có API key cho {prov} - vào trang Model dán key trước."
        return True, ""
    return False, f"Provider lạ: {prov}"


class _ApiAuxEngine:
    """Engine việc nền chạy bằng provider API, mang hợp đồng của ClaudeSDK.

    Công cụ lấy từ hub (builtin file vault + MCP). Hub tự chặn ghi khi mode=suggest, nên
    loop chế độ chỉ-đọc vẫn chỉ-đọc dù chạy trên engine này.
    """

    def __init__(self, provider, model, system_prompt=None, vault_root=None,
                 mode="full", tag="aux", reasoning="off"):
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.vault_root = vault_root
        self.javis_mode = mode
        self.tag = tag
        self.reasoning = reasoning
        self.session_id = None      # engine API không có phiên nối tiếp - giữ cho đủ hợp đồng

    def is_available(self) -> bool:
        return bool(api_key_for(self.provider))

    def reset_session(self):
        self.session_id = None

    async def query(self, prompt: str):
        import engine as eng
        import mcp_hub

        key = api_key_for(self.provider)
        if not key:
            yield {"type": "error", "content": f"Chưa có API key cho {self.provider}."}
            return

        tools, route = [], {}
        try:
            tools, route = await mcp_hub.discover_all(self.javis_mode or "full",
                                                      vault_root=self.vault_root)
        except Exception as e:
            print(f"[aux discover] {e}", file=sys.stderr)

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})

        if tools:
            fn = {"openrouter": eng.openrouter_chat_with_mcp,
                  "openai": eng.openai_chat_with_mcp,
                  "gemini": eng.gemini_chat_with_mcp,
                  "anthropic-api": eng.anthropic_chat_with_mcp}[self.provider]
            stream = fn(key, self.model, messages, self.reasoning, tools, route)
        else:
            fn = {"openrouter": eng.openrouter_stream, "openai": eng.openai_stream,
                  "gemini": eng.gemini_stream, "anthropic-api": eng.anthropic_stream}[self.provider]
            stream = fn(key, self.model, messages, self.reasoning)

        # Đường API sinh "text" theo mảnh; việc nền chỉ đọc "final" nên gom lại rồi phát MỘT lần.
        buf = []
        async for ev in stream:
            t = ev.get("type")
            if t == "text":
                buf.append(ev.get("content") or "")
            elif t in ("tool_call", "error", "usage"):
                yield ev
                if t == "error":
                    return
        yield {"type": "final", "content": "".join(buf)}


def _build_api(spec, claude_cli_obj, mode, tag):
    return _ApiAuxEngine(
        provider=spec["provider"],
        model=spec.get("model") or "",
        system_prompt=getattr(claude_cli_obj, "system_prompt", None),
        vault_root=getattr(claude_cli_obj, "javis_vault", None),
        mode=mode or getattr(claude_cli_obj, "javis_mode", None) or "full",
        tag=tag or getattr(claude_cli_obj, "tag", "aux"),
    )


def _build_codex(spec, claude_cli_obj, mode, tag, codex_profile=None):
    from claude_cli import CodexCLI
    cc = CodexCLI(cwd=getattr(claude_cli_obj, "cwd", None),
                  tag=tag or getattr(claude_cli_obj, "tag", "aux"),
                  model=spec.get("model") or None,
                  instructions=getattr(claude_cli_obj, "system_prompt", None))
    # Codex không có allowlist per-call như Claude → chặn ở tầng sandbox của chính nó.
    cc.sandbox = _CODEX_SANDBOX.get(mode or getattr(claude_cli_obj, "javis_mode", None) or "full")
    if codex_profile:
        try:
            cc.profile = codex_profile()   # profile javis = thấy MCP của Javis (POS, connector...)
        except Exception as e:
            print(f"[aux codex profile] {e}", file=sys.stderr)
    return cc


def apply(deps, cli, mode: str = None, tag: str = None):
    """Dùng ở các nơi chạy nền sau khi đã dựng xong engine Claude.

    deps.aux_swap được main tiêm; thiếu nó (unit test dựng deps tối giản) thì rơi về cách
    cũ - chỉ đặt model - nên test cũ không phải sửa và hành vi không đổi.
    """
    fn = getattr(deps, "aux_swap", None)
    if fn:
        return fn(cli, mode=mode, tag=tag)
    getter = getattr(deps, "aux_model", None)
    if getter:
        cli.model = getter() or None
    return cli


def swap(cli, mode: str = None, tag: str = None, spec: dict = None,
         codex_profile=None, settings: dict = None):
    """Engine Claude đã dựng -> engine theo model việc nền người dùng chọn.

    Mặc định (hoặc provider lạ / thiếu key) thì TRẢ LẠI NGUYÊN engine Claude: đổi model nền
    là tuỳ chọn, hỏng cấu hình thì việc nền phải vẫn chạy chứ không được chết.
    """
    try:
        sp = spec if spec is not None else read_spec(settings)
        prov = sp.get("provider", CLAUDE)
        if prov == CLAUDE:
            cli.model = sp.get("model") or None
            return cli
        ok, why = availability(sp, settings)
        if not ok:
            print(f"[aux] {why} → việc nền tạm dùng lại Claude.", file=sys.stderr)
            return cli
        if prov == CODEX:
            return _build_codex(sp, cli, mode, tag, codex_profile)
        if prov in API_PROVIDERS:
            return _build_api(sp, cli, mode, tag)
    except Exception as e:
        print(f"[aux swap] {e} → giữ engine Claude.", file=sys.stderr)
    return cli
