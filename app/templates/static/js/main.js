console.log("Main JS loaded (improved)");

// Utility helpers
function setToken(token) {
  try {
    localStorage.setItem("access_token", token);
  } catch (e) {
    console.warn("Could not set token in localStorage:", e);
  }
}

function getToken() {
  return localStorage.getItem("access_token");
}

function showAlert(msg) {
  // Customize: you can update this to show a nicer UI alert
  alert(msg);
}

// Replace page content with fetched HTML (safe single-page-like navigation)
async function loadAndRenderPage(url) {
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        "Accept": "text/html",
        "X-Requested-With": "XMLHttpRequest"
      }
    });

    if (!res.ok) {
      console.error("Failed to fetch page:", url, res.status);
      showAlert("Failed to load page. Check logs.");
      return false;
    }

    const html = await res.text();

    // Replace body/content - keep <head> intact so CSS/JS keeps loaded.
    // Option A: Replace body entirely
    document.documentElement.innerHTML = html;

    // Update browser URL without reloading
    window.history.pushState({}, "", url);

    // Re-run any inline scripts if necessary (optional)
    // (If your admin dashboard depends on additional JS files, ensure they are loaded via proper <script src> tags that are absolute/relative and accessible.)

    return true;
  } catch (err) {
    console.error("Error loading page:", err);
    showAlert("Error loading page. See console for details.");
    return false;
  }
}

// Generic form submit via fetch for endpoints that return JSON { success, redirect, token }
async function handleAuthForm(formSelector, endpoint, extraHandler = null) {
  const form = document.querySelector(formSelector);
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(form);
    // send as form-encoded
    const payload = new URLSearchParams();
    for (const pair of formData.entries()) payload.append(pair[0], pair[1]);

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        body: payload,
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      });

      const data = await res.json();

      if (!data || !data.success) {
        const errMsg = data?.error || "Authentication failed";
        console.warn("Auth error:", errMsg);
        showAlert(errMsg);
        return;
      }

      // store token if provided
      if (data.token) setToken(data.token);

      // if extraHandler is provided, call it (for special flows)
      if (typeof extraHandler === "function") await extraHandler(data);

      // If redirect URL returned, fetch and inject HTML instead of full reload
      const redirect = data.redirect;
      if (redirect) {
        // Try to load the redirect content and replace page (avoids iframe/navigate issues)
        const ok = await loadAndRenderPage(redirect);
        if (!ok) {
          // fallback to changing location (last resort)
          window.location.href = redirect;
        }
      } else {
        // If no redirect provided, you may show a success message or load default dashboard
        showAlert("Login successful");
      }
    } catch (err) {
      console.error("Auth request failed:", err);
      showAlert("Network error. See console for details.");
    }
  });
}

// Attach to login / admin login / signup forms if present
document.addEventListener("DOMContentLoaded", () => {
  // example selectors - ensure your templates have these IDs
  handleAuthForm("#loginForm", "/login");
  handleAuthForm("#signupForm", "/signup");
  handleAuthForm("#adminLoginForm", "/admin/login");

  // Handle browser back/forward so history navigation loads pages via AJAX
  window.addEventListener("popstate", async (e) => {
    // On popstate, try to re-load the current path via fetch
    const path = window.location.pathname || "/";
    await loadAndRenderPage(path);
  });

  // Debug info
  console.log("Auth handlers attached. Token present:", !!getToken());
});
