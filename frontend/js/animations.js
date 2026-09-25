/**
 * Animation Utilities for MRPL Sovereign AI Workstation UI.
 * Fast, subtle 180ms panel entrance micro-interactions.
 */

const Animations = {
  animateViewEntrance(element) {
    if (!element) return;
    
    if (window.gsap) {
      gsap.fromTo(element, 
        { opacity: 0, y: 4 },
        { opacity: 1, y: 0, duration: 0.18, ease: "power2.out" }
      );
    } else {
      element.style.animation = 'none';
      element.offsetHeight; // trigger reflow
      element.style.animation = 'panel-in 0.18s cubic-bezier(0.16, 1, 0.3, 1) forwards';
    }
  }
};

window.Animations = Animations;
