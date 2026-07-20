---
hide:
  - navigation
  - toc
---

<main class="home-prototype prototype--editorial" data-prototype="editorial">
  <header class="prototype-bar">
    <a class="prototype-brand" href="../../"><span>OS</span> Selected open-source work</a>
    <span>Public engineering / 2026</span>
  </header>
  <section class="editorial-hero">
    <div class="editorial-hero__title">
      <p class="prototype-kicker">Evgeny Aleshin · Open-source engineering</p>
      <h1>Dependable tools for complex systems.</h1>
    </div>
    <div class="editorial-hero__note">
      <p>This is the public side of my engineering practice: maintained libraries where API design, operational safety, and documentation are treated as one product.</p>
      <a href="#editorial-library-index">Explore selected work ↓</a>
    </div>
  </section>
  <section class="editorial-practice" aria-labelledby="editorial-practice-heading">
    <div class="editorial-practice__intro">
      <p class="prototype-kicker">Engineering practice</p>
      <h2 id="editorial-practice-heading">What I optimise for</h2>
    </div>
    <div class="editorial-practice__grid">
      <article>
        <span>01</span>
        <h3>Clear interfaces</h3>
        <p>Complex provider APIs become consistent, typed surfaces with predictable synchronous and asynchronous paths.</p>
      </article>
      <article>
        <span>02</span>
        <h3>Operational safety</h3>
        <p>Credentials, mutations, ambiguous outcomes, and provider failures are designed as explicit boundaries.</p>
      </article>
      <article>
        <span>03</span>
        <h3>Developer experience</h3>
        <p>Documentation, examples, release automation, and machine-readable contracts ship with the code.</p>
      </article>
    </div>
  </section>
  <section class="editorial-index" id="editorial-library-index" aria-label="Library registry">
    <div class="editorial-index__heading">
      <span>Selected work / 2026</span>
      <span>02 maintained projects</span>
      <span>Public code · released packages</span>
    </div>
    <article class="editorial-entry editorial-entry--live">
      <div class="editorial-entry__number">01</div>
      <div class="editorial-entry__body">
        <p class="editorial-entry__status">Maintained · released v3.0.1</p>
        <h2>IG Trading Library</h2>
        <p>A production-minded Python SDK for IG's trading APIs. It turns a fragmented provider surface into matching synchronous and asynchronous clients, typed models, guarded mutations, structured failures, streaming abstractions, and versioned documentation.</p>
        <ul><li>API architecture</li><li>Real-time systems</li><li>Safety-first automation</li><li>Release engineering</li></ul>
      </div>
      <div class="editorial-entry__actions">
        <a href="https://evgesha9400.github.io/ig-trading-lib/latest/">IG documentation</a>
        <a href="https://github.com/evgesha9400/ig-trading-lib">IG source</a>
        <a href="https://pypi.org/project/ig-trading-lib/">IG package</a>
        <code>pip install ig-trading-lib</code>
      </div>
    </article>
    <article class="editorial-entry">
      <div class="editorial-entry__number">02</div>
      <div class="editorial-entry__body">
        <p class="editorial-entry__status">Maintained · reference in development</p>
        <h2>KuCoin Futures Library</h2>
        <p>A focused wrapper around KuCoin Futures for market data, orders, account workflows, and websocket automation. The project explores composable trading primitives and reusable event-driven clients.</p>
        <ul><li>Trading automation</li><li>Exchange integration</li><li>Websocket clients</li><li>Reusable execution helpers</li></ul>
      </div>
      <div class="editorial-entry__actions">
        <span>Documentation will accompany the next release</span>
        <a href="https://github.com/evgesha9400/kucoin-futures-lib">KuCoin source</a>
        <a href="https://pypi.org/project/kucoin-futures-lib/">KuCoin package</a>
        <code>pip install kucoin-futures-lib</code>
      </div>
    </article>
  </section>
  <footer class="prototype-footer">
    <span>Open source makes engineering judgment inspectable.</span>
    <a href="https://github.com/evgesha9400">More work on GitHub ↗</a>
  </footer>
</main>
