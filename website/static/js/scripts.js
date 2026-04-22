(function () {
  var backgroundVideo = document.querySelector(".site-background-video");
  var nav = document.getElementById("nav-links");
  var toggle = document.querySelector(".nav-toggle");

  function startBackgroundVideo() {
    if (!backgroundVideo) {
      return;
    }

    var playAttempt = backgroundVideo.play();
    if (playAttempt && typeof playAttempt.catch === "function") {
      playAttempt.catch(function () {
        // Ignore autoplay rejections and leave the poster/background image in place.
      });
    }
  }

  if (backgroundVideo) {
    backgroundVideo.muted = true;
    startBackgroundVideo();
    backgroundVideo.addEventListener("loadedmetadata", startBackgroundVideo, {
      once: true,
    });
  }

  function setMenuState(isOpen) {
    if (!toggle || !nav) {
      return;
    }

    nav.classList.toggle("is-open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute(
      "aria-label",
      isOpen ? "Close navigation menu" : "Open navigation menu",
    );
  }

  if (toggle && nav) {
    setMenuState(false);

    toggle.addEventListener("click", function () {
      var isOpen = !nav.classList.contains("is-open");
      setMenuState(isOpen);
    });

    nav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        setMenuState(false);
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        setMenuState(false);
      }
    });
  }

  var page = document.body.getAttribute("data-page");
  var links = document.querySelectorAll(".nav-links a");

  links.forEach(function (link) {
    var navTarget = link.getAttribute("data-nav") || "";
    if (navTarget === page || (page === "film" && navTarget === "showtimes")) {
      link.classList.add("is-active");
      link.setAttribute("aria-current", "page");
    }
  });

  document.querySelectorAll("[data-current-year]").forEach(function (node) {
    node.textContent = String(new Date().getFullYear());
  });
})();
