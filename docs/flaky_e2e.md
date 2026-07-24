# 不稳定 E2E 用例追踪

记录因网络波动、政府站点响应不稳定等原因偶发失败的端到端测试。这些失败不是代码缺陷，不应阻塞 CI，但需要追踪以便后续加入重试机制。

## 已记录用例

### test_ahbz_cross_check_with_stdgov

- **文件**: `tests/test_e2e_adapters.py::TestE2ECrossAdapter::test_ahbz_cross_check_with_stdgov`
- **首次记录**: 2026-07-24 (Q22-02 全量回归时偶发失败)
- **失败模式**: 全量测试中失败，隔离重跑通过。根因是 ahbz/std_gov 政府站点响应时间不稳定。
- **影响**: 不影响代码正确性，仅在 CI 全量运行时可能因网络超时误报。
- **建议**: 后续为 E2E 套件增加 pytest-rerunfailures 或自定义重试装饰器，失败时自动重试 2 次。
