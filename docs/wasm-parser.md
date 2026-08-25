# wasm 解析器（webdemo.wasm）使用说明

站点内置了 Samsaadhanii-mbt 编译出的客户端梵语解析器：sandhi 切分 +
三脚本转写 + 形态分析，全部在浏览器本地完成，无服务端调用。

- 产物：`public/wasm/webdemo.wasm`（1,432,813 B ≈ 1.36 MiB；CDN 开
  brotli 后约 267 KB）
- 封装：`src/parser-wasm.ts`（类型化、total——失败返回 `null`/`""`，不抛错）
- 许可：GPL-2.0（代码层）；数据来源分层见 `public/wasm/LICENSE`
- 权威 schema：moonbit-samsaadhanii `docs/integration-guide.md` §3
  （`src/webdemo/api.mbt`）

## 三行接入

底层 instantiate 就是三行（js-string builtins 模式，字符串原生互通）：

```js
const bytes = await (await fetch('./wasm/webdemo.wasm')).arrayBuffer();
const { instance } = await WebAssembly.instantiate(bytes, {}, {
  builtins: ['js-string'], importedStringConstants: '_',
});
```

日常请直接用封装模块，不必碰 instantiate：

```ts
import { initParser, analyzeWord, morphLookup, translit3, warmup } from "./parser-wasm";

await initParser();                       // true = 可用；false = 不支持/产物缺失
const r = analyzeWord("रामास्ति");          // → { candidates: [{ parts_deva: ["राम","अस्ति"], ... }] }
const m = morphLookup(r!.candidates[0].parts_deva[1]); // → अस्ति → lemma "as", pos "verb"
translit3("राम", "iast");                  // → "rāma"
warmup();                                 // 页面空闲时预热，首点词免 ~80ms 冷启动
```

建议在页面加载后调一次 `warmup()`（内部用 requestIdleCallback，幂等），
不要同步阻塞首屏。

## ?wasm=1 flag 建议

推广到默认开启之前，建议先挂 opt-in flag 做灰度：

```ts
const enableWasm =
  new URLSearchParams(location.search).has("wasm") || localStorage.getItem("wasm") === "1";
if (enableWasm) warmup();
```

- 带 `?wasm=1` 访问 → 加载解析器并启用点词增强；
- 其余访客 → 完全不拉取这 1.4 MB，正文照常。
- 稳定后把判断改为常开即可（封装本身对不支持的浏览器自动降级）。

## 降级语义

`parser-wasm.ts` 的所有函数都是 total 的：

| 场景 | 表现 |
|---|---|
| 浏览器不支持（需 WasmGC + JS String Builtins；Chrome/Edge ≥131、Firefox ≥138、Safari ≥18.4） | `initParser()` 返回 `false`；后续调用返回 `null`/`""` |
| wasm 文件缺失 / 校验失败 | 同上 |
| 查询词不在 morph 子集内 | `morphLookup` 返回 `{found:false, analyses:[]}` ——诚实缺省，不是错误 |

因此接线侧只需写正常路径：拿到 `null` 就回落到既有行为（如跳转在线词典），
正文渲染永不依赖本模块。兼容矩阵与混合 shard 架构见 integration-guide §4–5。

注意两点：
- `analyze_word` 候选最多返回 8 条，全量数在 `total` 字段；
- `translit3(x,"itrans")` 在探测为非空前视为不可用（T2 已落地，但保留探测习惯）。

## 再同步产物

wasm 是从姊妹仓库复制进来的二进制，**不手改、不进 git LFS 之外的特殊流程**。
上游重建后同步：

```bash
scripts/fetch-wasm.sh        # 默认源 ../moonbit-samsaadhanii/web/dist
# 或显式指定源目录：
scripts/fetch-wasm.sh /path/to/moonbit-samsaadhanii/web/dist
```

脚本会打印两侧大小 + SHA-256 并校验一致。若指纹变化，记得更新
`public/wasm/LICENSE` 底部的 SHA-256 行。需要改数据切片（更大 morph 子集等）
时先在上游重新生成，见 integration-guide §8。
