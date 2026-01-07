# Coding rules for ChatGPT / Codex

1. 不要写防御性编程，假设输入数据和类型是合法的，除非我在提问中特别说明需要做健壮性处理。

2. 避免使用 `try/except` 包裹整段代码或整个函数。
   - 只在**明确需要特殊处理**的语句周围使用 `try/except`（例如需要记录日志或返回默认值）。
   - 不要用 `try/except` 来做普通的条件判断或控制流程。

3. 除非我特别要求：
   - 不要使用 `hasattr()`、`getattr()` 来检查属性是否存在；
   - 假设对象的属性是已知且存在的；
   - 不要大量使用 `is None` / 空字符串 / 空列表等检查，只保留函数语义上必需的检查。

4. 生成的代码和注释中**不要包含任何中文字符**。所有标识符和注释一律使用英文。

---

English version (for better model understanding):

1. Do **not** use defensive programming. Assume that the input data and types are valid, unless I explicitly ask for robust input validation.

2. Avoid using `try/except` around whole functions or large blocks.
   - Use `try/except` only around specific operations that may fail and that require special handling (logging, fallback value, etc.).
   - Do not use exceptions as normal control flow.

3. Unless explicitly requested:
   - Do not use `hasattr()` or `getattr()` to check for attributes.
   - Assume required attributes exist on the objects.
   - Do not add lots of `is None` / emptiness checks. Keep only the ones that are essential to the function contract.

4. Do not output any Chinese characters in code or comments. Use English only.
