# {{ cookiecutter.adapter_name }} 适配器

- **站点**: {{ cookiecutter.site_label }}
- **URL**: {{ cookiecutter.base_url }}{{ cookiecutter.search_endpoint }}
- **架构**: {{ cookiecutter.response_type }}
- **方法**: {{ cookiecutter.method }}
- **编码**: {{ cookiecutter.encoding }}

## 使用

```python
from pilotstd.query.adapters.{{ cookiecutter.adapter_name }} import {{ cookiecutter.adapter_class }}
adapter = {{ cookiecutter.adapter_class }}()
results = adapter.query_standards("GB/T")
```

## 运行测试

```bash
pytest tests/test_{{ cookiecutter.adapter_name }}.py -v
```
