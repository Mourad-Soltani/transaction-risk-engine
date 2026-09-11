// Author: Mourad.Soltani
(function () {
  "use strict";

  function setOutput(el, obj) {
    // textContent only. User-supplied strings never touch innerHTML.
    el.textContent = JSON.stringify(obj, null, 2);
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let data;
    try {
      data = await res.json();
    } catch (_e) {
      data = { error: "non_json_response", status: res.status };
    }
    return data;
  }

  function parseField(el) {
    try {
      return { ok: true, value: JSON.parse(el.value) };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const assessEl = document.getElementById("assess-payload");
    const screenEl = document.getElementById("screen-payload");
    const assessOut = document.getElementById("assess-out");
    const screenOut = document.getElementById("screen-out");

    document.getElementById("assess-btn").addEventListener("click", async function () {
      const p = parseField(assessEl);
      if (!p.ok) {
        setOutput(assessOut, { error: "invalid_json", detail: p.error });
        return;
      }
      setOutput(assessOut, await postJson("/api/assess", p.value));
    });

    document.getElementById("screen-btn").addEventListener("click", async function () {
      const p = parseField(screenEl);
      if (!p.ok) {
        setOutput(screenOut, { error: "invalid_json", detail: p.error });
        return;
      }
      setOutput(screenOut, await postJson("/api/screen", p.value));
    });
  });
})();
