// Browser-side instrumentation. Python drives the browser; Node.js is not required.
(() => {
  window.__configProbe = {keys: [], alphabets: [], errors: [], instrumented: 0};
  const originalEval = window.eval;
  window.eval = function(source) {
    if (typeof source === 'string' && source.length > 50000) {
      const scheduler = /function ([$\w]+)\(([$\w]+),([$\w]+),([$\w]+)\)\{var [^;]+;([$\w]+)=\2,\2\[/.exec(source);
      const encoder = /function ([$\w]+)\(([$\w]+),([$\w]+)\)\{var [^;]+;[^{}]{0,500}?\3=\3\|\|([$\w]+),/.exec(source);
      if (scheduler && encoder) {
        const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const chunk = source.slice(scheduler.index, scheduler.index + 800);
        const normalized = new RegExp('([$\\w]+)=([$\\w]+)\\(' + escape(scheduler[5]) + '\\),').exec(chunk);
        if (normalized) {
          const location = scheduler.index + normalized.index;
          const replacement = normalized[1] + '=(window.__configProbe.keys.push(Array.from(' + scheduler[5] + ')),' + normalized[2] + '(' + scheduler[5] + ')),';
          source = source.slice(0, location) + replacement + source.slice(location + normalized[0].length);
          const assignment = encoder[3] + '=' + encoder[3] + '||' + encoder[4] + ',';
          source = source.replace(assignment, () => assignment + 'window.__configProbe.alphabets.push(Array.from(' + encoder[3] + ').slice(0,64).join("")),');
          window.__configProbe.instrumented++;
        } else window.__configProbe.errors.push('AES normalized key location not found');
      } else window.__configProbe.errors.push('AES/Base64 structural signatures not found');
    }
    return originalEval.call(window, source);
  };
})();
