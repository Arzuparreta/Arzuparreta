// @ts-nocheck — Motion generic targets vs DOM elements (library typings)
import { inView, animate } from "motion";

function initReveals() {
  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  document.querySelectorAll("[data-reveal]").forEach((el) => {
    if (!(el instanceof HTMLElement)) return;
    if (reduceMotion) {
      el.style.opacity = "1";
      el.style.transform = "none";
      return;
    }
    el.style.opacity = "0";
    el.style.transform = "translateY(1.25rem)";
    inView(
      el,
      () => {
        animate(
          el,
          {
            opacity: [0, 1],
            transform: ["translateY(1.25rem)", "translateY(0)"],
          },
          { duration: 0.55, easing: [0.22, 1, 0.36, 1] },
        );
      },
      { margin: "-8% 0px -8% 0px" },
    );
  });
}

initReveals();
