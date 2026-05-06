// SPA Navigation - AJAX page load without full reload
(function() {
  // Run after page content is swapped
  function runPageInit() {
    // Dispatch custom event for page-specific init
    var event = new CustomEvent('pageReady');
    document.dispatchEvent(event);
  }

  document.addEventListener('click', function(e) {
    var link = e.target.closest('.nav-btn');
    if (!link || link.host !== location.host) return;
    e.preventDefault();
    var url = link.pathname;
    if (url === location.pathname) return;

    var main = document.querySelector('.main');
    main.style.opacity = '0.4';
    main.style.transition = 'opacity 0.15s';

    fetch(url)
      .then(function(r) { return r.text(); })
      .then(function(html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        var newMain = doc.querySelector('.main');
        if (newMain) {
          main.innerHTML = newMain.innerHTML;
          document.title = doc.title;
          history.pushState(null, '', url);
          // Re-execute all scripts in the new content
          var scripts = main.querySelectorAll('script');
          for (var i = 0; i < scripts.length; i++) {
            var old = scripts[i];
            var s = document.createElement('script');
            if (old.src) { s.src = old.src; } else { s.textContent = old.textContent; }
            old.parentNode.replaceChild(s, old);
          }
          // Trigger page init
          runPageInit();
        }
        main.style.opacity = '1';
      })
      .catch(function() { window.location.href = url; });
  });

  window.addEventListener('popstate', function() {
    location.reload();
  });
})();
