-- 自动化系统数据库导出
-- 时间: 2025-03-30 23:49:23
-- 源数据库: automation.db
-- 导出工具: SQL导出工具

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 表 schema_version
DROP TABLE IF EXISTS schema_version;
CREATE TABLE schema_version (
                    version INTEGER PRIMARY KEY
                );

-- 表 schema_version 的数据
INSERT INTO schema_version (version) VALUES (1);

-- 表 apps
DROP TABLE IF EXISTS apps;
CREATE TABLE apps (
                    app_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    package_name TEXT,
                    priority INTEGER DEFAULT 5,
                    time_slice INTEGER DEFAULT 3600,  -- Default 1 hour
                    daily_limit INTEGER DEFAULT 7200, -- Default 2 hours
                    reset_time TEXT DEFAULT '04:00',  -- Default 4 AM
                    status TEXT DEFAULT 'inactive',
                    config TEXT,                      -- JSON config
                    last_update INTEGER
                );

-- 表 apps 的数据
INSERT INTO apps (app_id, name, package_name, priority, time_slice, daily_limit, reset_time, status, config, last_update) VALUES ('three_kingdoms', '三国杀', 'com.yoka.sanguosha', 5, 7200, 14400, '04:00', 'active', '{"screen_width":720,"screen_height":1280,"ocr_interval":0.5,"recognition_threshold":0.8}', NULL);

-- 表 accounts
DROP TABLE IF EXISTS accounts;
CREATE TABLE accounts (
                    account_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    username TEXT,
                    password TEXT,
                    login_type TEXT DEFAULT 'default',
                    last_login_time INTEGER,
                    total_runtime INTEGER DEFAULT 0,
                    daily_runtime INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    extra_data TEXT,                  -- JSON data
                    FOREIGN KEY (app_id) REFERENCES apps(app_id)
                );

-- 表 tasks
DROP TABLE IF EXISTS tasks;
CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    parent_id TEXT,                  -- Parent task ID
                    type TEXT DEFAULT 'daily',       -- daily, weekly, etc.
                    priority INTEGER DEFAULT 5,
                    max_retries INTEGER DEFAULT 3,
                    timeout INTEGER DEFAULT 300,     -- 5 minutes default
                    description TEXT,
                    config TEXT,                     -- JSON config
                    handler_class TEXT,              -- Python class name
                    enabled INTEGER DEFAULT 1,       -- Boolean
                    FOREIGN KEY (app_id) REFERENCES apps(app_id),
                    FOREIGN KEY (parent_id) REFERENCES tasks(task_id)
                );

-- 表 tasks 的数据
INSERT INTO tasks (task_id, app_id, name, parent_id, type, priority, max_retries, timeout, description, config, handler_class, enabled) VALUES ('task_daily_signin', 'three_kingdoms', '每日签到', NULL, 'daily', 10, 3, 300, NULL, '{"max_retry":3,"timeout":300}', 'SignInTask', 1);
INSERT INTO tasks (task_id, app_id, name, parent_id, type, priority, max_retries, timeout, description, config, handler_class, enabled) VALUES ('task_yuanbao_tree', 'three_kingdoms', '元宝树', NULL, 'daily', 9, 3, 300, NULL, '{"max_retry":3,"timeout":300}', 'YuanbaoTreeTask', 1);
INSERT INTO tasks (task_id, app_id, name, parent_id, type, priority, max_retries, timeout, description, config, handler_class, enabled) VALUES ('task_campaign', 'three_kingdoms', '征战天下', NULL, 'daily', 8, 3, 300, NULL, '{"max_retry":3,"timeout":600,"stamina_threshold":40}', 'CampaignTask', 1);
INSERT INTO tasks (task_id, app_id, name, parent_id, type, priority, max_retries, timeout, description, config, handler_class, enabled) VALUES ('task_battle', 'three_kingdoms', '军争演练', NULL, 'daily', 7, 3, 300, NULL, '{"max_retry":3,"timeout":1800,"battle_count":5,"battle_type":"military"}', 'BattleTask', 1);
INSERT INTO tasks (task_id, app_id, name, parent_id, type, priority, max_retries, timeout, description, config, handler_class, enabled) VALUES ('task_5101571d', 'three_kingdoms', '三国杀日常任务', NULL, 'daily', 5, 3, 300, NULL, NULL, 'tasks.three_kingdoms.main_task.ThreeKingdomsTask', 1);
INSERT INTO tasks (task_id, app_id, name, parent_id, type, priority, max_retries, timeout, description, config, handler_class, enabled) VALUES ('task_2649e3d8', 'three_kingdoms', '三国杀日常任务', NULL, 'daily', 5, 3, 300, NULL, NULL, 'tasks.three_kingdoms.main_task.ThreeKingdomsTask', 1);

-- 表 task_status
DROP TABLE IF EXISTS task_status;
CREATE TABLE task_status (
                    status_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    completed INTEGER DEFAULT 0,       -- Boolean
                    completion_time INTEGER,           -- Timestamp
                    last_run_time INTEGER,             -- Timestamp
                    retry_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    execution_data TEXT,               -- JSON data
                    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
                    UNIQUE(account_id, task_id)
                );

-- 表 recognition_states
DROP TABLE IF EXISTS recognition_states;
CREATE TABLE recognition_states (
                    state_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,              -- text, image
                    config TEXT NOT NULL,            -- JSON config
                    FOREIGN KEY (app_id) REFERENCES apps(app_id)
                );

-- 表 actions
DROP TABLE IF EXISTS actions;
CREATE TABLE actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    name TEXT NOT NULL,
                    function_name TEXT NOT NULL,
                    params TEXT,                     -- JSON parameters
                    FOREIGN KEY (from_state) REFERENCES recognition_states(state_id),
                    FOREIGN KEY (to_state) REFERENCES recognition_states(state_id)
                );

-- 表 settings
DROP TABLE IF EXISTS settings;
CREATE TABLE settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT
                );

-- 表 settings 的数据
INSERT INTO settings (key, value, description) VALUES ('screen_recognition_interval', '0.5', '屏幕识别间隔(秒)');
INSERT INTO settings (key, value, description) VALUES ('battle_recognition_interval', '0.3', '战斗中屏幕识别间隔(秒)');
INSERT INTO settings (key, value, description) VALUES ('max_loading_wait', '30', '最大加载等待时间(秒)');
INSERT INTO settings (key, value, description) VALUES ('max_retry_count', '3', '操作最大重试次数');
INSERT INTO settings (key, value, description) VALUES ('app_restart_timeout', '300', '应用重启超时时间(秒)');

-- 表 activity_log
DROP TABLE IF EXISTS activity_log;
CREATE TABLE activity_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    app_id TEXT,
                    account_id TEXT,
                    task_id TEXT,
                    action TEXT,
                    status TEXT,
                    details TEXT
                );

COMMIT;
PRAGMA foreign_keys = ON;
