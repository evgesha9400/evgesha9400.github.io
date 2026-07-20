---
hide:
  - navigation
  - toc
---

<main class="home-prototype prototype--editorial" data-prototype="editorial">
  <section class="editorial-hero">
    <div class="editorial-hero__title">
      <p class="prototype-kicker">Open-source libraries</p>
      <h1>Open-source Python libraries.</h1>
    </div>
    <div class="editorial-hero__note">
      <p>A catalogue of Python libraries I maintain. Each entry links to its source code, published package, and release documentation where available.</p>
      <a href="#editorial-library-index">Browse projects ↓</a>
    </div>
  </section>
  <section class="editorial-practice" aria-labelledby="editorial-practice-heading">
    <div class="editorial-practice__intro">
      <p class="prototype-kicker">Current catalogue</p>
      <h2 id="editorial-practice-heading">Catalogue status</h2>
    </div>
    <div class="editorial-practice__grid">
      <article>
        <span>02</span>
        <h3>Public repositories</h3>
        <p>Both projects are public on GitHub.</p>
      </article>
      <article>
        <span>02</span>
        <h3>PyPI packages</h3>
        <p>Both projects are distributed through PyPI.</p>
      </article>
      <article>
        <span>01</span>
        <h3>Published documentation</h3>
        <p>Versioned documentation is published for IG Trading Library. The KuCoin Futures Library reference is in development.</p>
      </article>
    </div>
  </section>
  <section class="editorial-index" id="editorial-library-index" aria-label="Library registry">
    <div class="editorial-index__heading">
      <span>Selected work / 2026</span>
      <span>02 maintained projects</span>
      <span>Public code · released packages</span>
    </div>
    <article class="editorial-entry editorial-entry--live" data-library="ig-trading-lib">
      <div class="editorial-entry__number">01</div>
      <div class="editorial-entry__body">
        <p class="editorial-entry__status">Maintained · released v3.0.1</p>
        <h2>IG Trading Library</h2>
        <p>A Python client library for the IG REST and Lightstreamer APIs. It provides matching synchronous and asynchronous clients, typed response models, guarded live mutations, structured exceptions, pagination, endpoint-version facades, and versioned documentation.</p>
        <ul><li>REST and Lightstreamer</li><li>Sync and async</li><li>Typed models and errors</li><li>Versioned releases</li></ul>
      </div>
      <div class="editorial-entry__actions">
        <a href="https://evgesha9400.github.io/ig-trading-lib/latest/">IG Trading Library Documentation</a>
        <a href="https://github.com/evgesha9400/ig-trading-lib">IG Trading Library Source</a>
        <a href="https://pypi.org/project/ig-trading-lib/">IG Trading Library Package</a>
        <div class="editorial-install" id="ig-install-command" markdown>
```shell
pip install ig-trading-lib
```
        </div>
      </div>
    </article>
    <article class="editorial-entry" data-library="kucoin-futures-lib">
      <div class="editorial-entry__number">02</div>
      <div class="editorial-entry__body">
        <p class="editorial-entry__status">Maintained · reference in development</p>
        <h2>KuCoin Futures Library</h2>
        <p>A Python wrapper for KuCoin Futures market data, trading, account, and websocket workflows. It includes synchronous and asynchronous entry points, order helpers, OCO handling, and reusable websocket components.</p>
        <ul><li>Market and trade APIs</li><li>Account workflows</li><li>Websocket clients</li><li>Order helpers</li></ul>
      </div>
      <div class="editorial-entry__actions">
        <span>Documentation will accompany the next release</span>
        <a href="https://github.com/evgesha9400/kucoin-futures-lib">KuCoin Futures Library Source</a>
        <a href="https://pypi.org/project/kucoin-futures-lib/">KuCoin Futures Library Package</a>
        <div class="editorial-install" id="kucoin-install-command" markdown>
```shell
pip install kucoin-futures-lib
```
        </div>
      </div>
    </article>
  </section>
  <footer class="prototype-footer">
    <span>Maintained by Evgeny Aleshin.</span>
    <a href="https://github.com/evgesha9400">More work on GitHub ↗</a>
  </footer>
</main>
