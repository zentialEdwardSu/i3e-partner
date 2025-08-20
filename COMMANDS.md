# 初始化数据库
python main.py db init

# 列出所有作者
python main.py db list authors

# 列出所有论文（默认完整），并只保留每篇论文的 id/title/authors[].author_id
python main.py db list papers --fields id --fields title --fields "authors[].author_id"

# 同一效果（逗号分隔）
python main.py db list papers --fields "id,title,authors[].author_id"

# 查询单篇论文并只显示 title 与作者 id/name
python main.py db get paper_by_id 11124431 --keep title --fields "authors[].author_id" --fields "authors[].name"

# 导出数据库为 JSON，只保留作者 id 和论文 title
python main.py db export --output export.json --fields "authors[].author_id" --fields "papers[:].title"

# 列出 check != 1 的所有作者和论文 id
python main.py db unchecked all

# 使用交互策略（M）保存作者信息（抓取时会提示冲突字段选择）
python main.py ieee author --author-id 37290266200 --save-db --strategy M

# 抓取某篇 publication 并保存到 DB（策略 AN：总是用新数据覆盖）
python main.py ieee pub --publication-id 11124431 --save-db --strategy AN

# 获取作者的发表列表并仅保存为 stub papers（不抓取详情）
python main.py ieee publist --author-id 37290266200 --save-db --strategy AO

# 缓存管理：清理过期缓存
python main.py cache cleanup

# 缓存管理：列出缓存条目并显示对象类型
python main.py cache list --show-object

# 使用本地 sqlite 交互 shell(bash only)（脚本已提供）
# 交互式打开 DB（优先 -p 参数，其次环境变量 DB_PATH，其次默认 ieee.db）
./scripts/db_shell.sh -p mydb.sqlite3
# 或执行单条 SQL 并退出
./scripts/db_shell.sh -p mydb.sqlite3 -e "SELECT id, title FROM paper LIMIT 10;"
