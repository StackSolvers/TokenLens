const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const appCode = fs.readFileSync('app.js', 'utf8');

const noopElement = () => ({
    addEventListener() {},
    classList: { add() {}, remove() {} },
    textContent: '',
    value: '',
    style: {},
});

const sandbox = {
    assert,
    console,
    localStorage: {
        store: {},
        getItem(key) {
            return Object.prototype.hasOwnProperty.call(this.store, key) ? this.store[key] : null;
        },
        setItem(key, value) {
            this.store[key] = String(value);
        },
        removeItem(key) {
            delete this.store[key];
        },
    },
    document: {
        addEventListener() {},
        getElementById() {
            return noopElement();
        },
        querySelector() {
            return noopElement();
        },
        querySelectorAll() {
            return [];
        },
    },
    window: { devicePixelRatio: 1 },
    fetch() {
        throw new Error('network disabled in pricing test');
    },
};

vm.createContext(sandbox);
vm.runInContext(`${appCode}

serverConfig = {
    pricing: { mode: 'known_only' },
    billing: {
        agents: {
            codex: 'subscription',
            cline: 'recorded_or_metered'
        },
        model_prices: {
            'gpt-5.5': {
                input_per_1m: 5,
                cached_input_per_1m: 0.5,
                cache_write_per_1m: 5,
                output_per_1m: 30,
                source: 'test'
            },
            'gpt-4.4': {
                input_per_1m: 1,
                output_per_1m: 4,
                source: 'test'
            }
        }
    }
};

loadConfiguredPrices(serverConfig);

assert.strictEqual(getModelCostRate('gpt-5.5', 'codex'), null);
assert.strictEqual(getModelCostRate('gpt-5.5', 'cline').out, 30);
assert.strictEqual(getModelCostRate('gpt-5.5-2026-04-23', 'cline').in, 5);
assert.strictEqual(getModelCostRate('gpt-5.5-mini', 'cline'), null);
assert.strictEqual(getModelCostRate('gpt-4.4', 'cline').out, 4);

const priced = generationCostDetail({
    model: 'gpt-5.5',
    input_tokens: 1000000,
    cached_tokens: 0,
    cache_write_tokens: 0,
    output_tokens: 1000000
}, 'cline');
assert.strictEqual(formatCostDetail(priced), '$35.00');

const unpriced = generationCostDetail({
    model: 'unknown-model',
    input_tokens: 1000,
    output_tokens: 1000
}, 'cline');
assert.strictEqual(formatCostDetail(unpriced), 'N/A');

serverConfig.pricing.mode = 'fallback';
rateInput = 1;
rateOutput = 4;
assert.strictEqual(getModelCostRate('unknown-model', 'cline').out, 4);
`, sandbox, { filename: 'app.js.pricing-test' });

console.log('dashboard pricing tests passed');
