-- 插入新的RPA流程配置到 task_processes 表
INSERT INTO `task_processes` (`id`, `task_name`, `chinese_name`, `process_detail_uuid`, `version`, `process_param`, `created_at`, `updated_at`)
VALUES
    (
      (SELECT * FROM (SELECT COALESCE(MAX(id), 0) + 1 FROM `task_processes`) AS temp),
      'CHINA_SOUTHERN_AIR_APPROVAL_DATA', 
      '南航订舱-批复数据获取', 
      '279df38a1502d93125024b753b7ff6a4', 
      '0.0.2', 
      '{"address_of_the_application_executable_file_tangyi":"C:\\\\Users\\\\Dell\\\\AppData\\\\Local\\\\Apps\\\\2.0\\\\YD4PNP7G.2OK\\\\GG45OYOT.8CO\\\\tang..tion_a34291f01d17e3f1_0003.0002_a265daa8fc6d4296\\\\Tang.Face.Main.exe","system_account":"SZXFED","login_password":"fengde123456++"}', 
      CURRENT_TIMESTAMP, 
      CURRENT_TIMESTAMP
    );
