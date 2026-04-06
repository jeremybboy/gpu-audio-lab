(function () {
  const byId = (id) => document.getElementById(id);

  function isGitHubPages() {
    return /\.github\.io$/i.test(window.location.hostname || "");
  }

  function showBanner() {
    const el = byId("banner-local");
    const pages = byId("banner-pages");
    if (!el || !pages) return;
    if (isGitHubPages()) {
      el.hidden = true;
      pages.hidden = false;
    } else {
      el.hidden = false;
      pages.hidden = true;
    }
  }

  async function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function postJson(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const ct = r.headers.get("content-type") || "";
    if (!r.ok) {
      let msg = r.statusText;
      if (ct.includes("application/json")) {
        const j = await r.json();
        msg = j.error || JSON.stringify(j);
      } else {
        const t = await r.text();
        if (t) msg = t.slice(0, 500);
      }
      throw new Error(msg);
    }
    return r;
  }

  byId("btn-describe").addEventListener("click", async () => {
    const err = byId("err-describe");
    const ok = byId("ok-describe");
    err.textContent = "";
    ok.textContent = "";
    try {
      const describe = byId("describe").value.trim();
      const syx_template = byId("template").value.trim();
      const name = byId("out-name").value.trim() || "sound_export";
      if (!describe) throw new Error("Enter a sound description.");
      if (!syx_template) throw new Error("Enter a template basename.");
      const r = await postJson("/api/export_sound", {
        describe,
        syx_template,
        name,
      });
      const blob = await r.blob();
      const cd = r.headers.get("content-disposition") || "";
      const m = cd.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/i);
      let fn = `${name}.syx`;
      if (m && m[1]) fn = m[1].replace(/['"]/g, "");
      await downloadBlob(blob, fn);
      ok.textContent = `Downloaded ${fn}`;
    } catch (e) {
      err.textContent = e.message || String(e);
    }
  });

  byId("btn-profile").addEventListener("click", async () => {
    const err = byId("err-profile");
    const ok = byId("ok-profile");
    err.textContent = "";
    ok.textContent = "";
    try {
      const raw = byId("profile-json").value.trim();
      const syx_template = byId("template-profile").value.trim();
      const name = byId("out-name-profile").value.trim() || "from_profile";
      if (!raw) throw new Error("Paste timbre profile JSON.");
      if (!syx_template) throw new Error("Enter a template basename.");
      let profile;
      try {
        profile = JSON.parse(raw);
      } catch {
        throw new Error("Invalid JSON in profile field.");
      }
      const r = await postJson("/api/export_from_profile", {
        profile,
        syx_template,
        name,
        syx_overlay: byId("syx-overlay").value,
      });
      const blob = await r.blob();
      await downloadBlob(blob, `${name}.syx`);
      ok.textContent = `Downloaded ${name}.syx`;
    } catch (e) {
      err.textContent = e.message || String(e);
    }
  });

  showBanner();
})();
