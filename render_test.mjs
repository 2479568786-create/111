import fs from 'node:fs';
import vm from 'node:vm';

const ctx = {
  console,
  API: { get: async () => ({}), post: async () => ({}) },
  Router: { register: () => {} },
  window: {},
  lucide: { createIcons() {} },
  document: { getElementById: () => null, querySelectorAll: () => [], addEventListener() {} },
  escapeHtml: (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
  escapeAttr: (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
  proxyImage: (u) => u,
  setTimeout, clearTimeout,
};
ctx.globalThis = ctx;
vm.createContext(ctx);

const code = fs.readFileSync(process.argv[2], 'utf8');
vm.runInContext(code, ctx, { filename: 'seller-insights.js' });

const run = (script) => vm.runInContext(script, ctx);

function check(name, cond, extra = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
  if (!cond) process.exitCode = 1;
}

const skuData = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')).data;
const dayData = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')).data;
ctx.__sku = skuData;
ctx.__day = dayData;

// ---- 按商品汇总 ----
let html = run(`sellerInsightsState.view = 'analysis'; renderSellerInsightResults(__sku)`);
check('sku 视图含「个商品」', html.includes('个商品'));
check('sku 视图不画按天图', !html.includes('class="si-chart"'));
check('sku 视图提示切换按天', html.includes('按天拆分'));
const rowCount = (html.match(/<tr><td class="si-product">/g) || []).length;
check('sku 视图行数=返回行数', rowCount === skuData.rows.length, `rows=${skuData.rows.length}`);
check('sku 视图无重复SKU', new Set(skuData.rows.map((r) => r.dimensions[0].id)).size === skuData.rows.length);
check('变体标记出现', html.includes('si-variant-tag'));
check('合计行存在', html.includes('Ozon 汇总'));

// ---- 按天拆分 ----
let htmlDay = run('renderSellerInsightResults(__day)');
check('按天视图含「行（按天）」', htmlDay.includes('行（按天）'));
check('按天视图渲染柱状图', htmlDay.includes('class="si-chart"'));
const dayRows = (htmlDay.match(/<tr><td class="si-product">/g) || []).length;
check('按天视图行数=返回行数', dayRows === dayData.rows.length, `rows=${dayData.rows.length}`);

// 排序
html = run(`sellerInsightsState.sortByView = { analysis: { key: 'revenue', direction: 'asc' } }; renderSellerInsightResults(__sku)`);
check('切换排序后仍可渲染', html.includes('si-table'));

for (const view of ['funnel', 'leaders', 'search']) {
  const out = run(`sellerInsightsState.view = '${view}'; renderSellerInsightResults(__sku)`);
  check(`视图 ${view} 渲染正常`, out.includes('si-table'));
}
console.log('done');
