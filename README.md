# 网页爬虫示例

这是一个使用 Python 标准库实现的简易网页爬虫脚本：`crawler.py`。

## 功能
- 按广度优先策略抓取页面
- 可限制最大抓取页数与最大深度
- 可选仅抓取同域名链接
- 可选遵守 `robots.txt`
- 将结果导出为 CSV（URL、状态码、标题、深度、链接数量、错误信息）

## 使用方式

```bash
python3 crawler.py https://example.com --max-pages 20 --max-depth 1 --same-domain-only --output result.csv
```

查看帮助：

```bash
python3 crawler.py --help
```

## 输出样例
CSV 表头如下：

```text
url,status,title,depth,links_found,error
```
