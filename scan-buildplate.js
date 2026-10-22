const fs = require('fs');
const path = require('path');

const dir = 'C:\\Users\\24795\\.dsh\\skills\\seerfar-ozon-selection\\.cache';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));

const kw = /(пластин|подложк|магнитн|PEI|build ?plate|стол (для|печат)|платформ)/i;
const seen = new Map();
const out = [];

for (const f of files) {
  let j;
  try {
    j = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
  } catch (e) { continue; }
  const inner = j && j.data && j.data.data;
  if (!inner) continue;
  // product endpoint
  if (inner.product) {
    const p = inner.product;
    const title = p.title || '';
    if (kw.test(title)) {
      const key = p.sku;
      if (!seen.has(key)) {
        seen.set(key, 1);
        out.push({
          sku: p.sku, title, price: p.price,
          sales: inner.totalSales, revenue: inner.totalRevenue,
          sellerId: p.sellerId, sellerName: p.sellerName,
          fulfillment: p.fulfillment, upDays: p.upDays,
          grossMargin: p.grossMargin, ret: p.returnCancellationRate,
          sellerType: p.sellerType, cat: p.categoryInfo && p.categoryInfo.category && p.categoryInfo.category.id
        });
      }
    }
  }
  // report/category endpoints
  const recs = inner.records || inner.list || inner.products;
  if (Array.isArray(recs)) {
    for (const r of recs) {
      const title = r.title || r.name || '';
      if (kw.test(title)) {
        const key = r.sku || r.productId || r.offerId || title;
        if (!seen.has(key)) {
          seen.set(key, 1);
          out.push({
            sku: r.sku, title, price: r.price,
            sales: r.sales ?? r.monthlySales ?? r.totalSales,
            revenue: r.revenue, sellerId: r.sellerId,
            sellerName: r.sellerName, fulfillment: r.fulfillment,
            upDays: r.upDays, grossMargin: r.grossMargin,
            ret: r.returnCancellationRate, sellerType: r.sellerType,
            cat: r.categoryId || (r.categoryInfo && r.categoryInfo.category && r.categoryInfo.category.id)
          });
        }
      }
    }
  }
}

// sort by sales desc
out.sort((a,b) => (b.sales||0) - (a.sales||0));
console.log('TOTAL MATCHES:', out.length);
for (const o of out) {
  console.log([o.sku, (o.sales||'-'), (o.price||'-')+'₽', '退'+(o.ret==null?'-':o.ret)+'%', '毛利'+(o.grossMargin==null?'-':o.grossMargin)+'%', '上架'+(o.upDays==null?'-':o.upDays)+'天', '跨境'+(o.sellerType===1?'Y':'N'), (o.fulfillment||[]).join('/'), o.sellerName||'-', o.title].join(' | '));
}
