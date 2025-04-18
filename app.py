#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import logging
import schedule
from datetime import datetime
import requests
import json
from pathlib import Path
import configparser
import argparse
import humanize
import locale
import time
import re

# 设置时区和语言环境
try:
    locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except:
        pass

# 确保日志目录存在
log_dir = '/app/output'
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'seeding_checker.log')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger('seeding_checker')

# 从配置文件加载配置
def load_config(config_file='config.ini'):
    logger.info(f"尝试加载配置文件: {config_file}")
    
    # 检查配置文件是否存在
    if not os.path.exists(config_file):
        logger.error(f"配置文件不存在: {config_file}")
        # 尝试在其他可能的位置查找配置文件
        possible_locations = [
            '/app/config/config.ini',
            '/app/config.ini',
            'config/config.ini',
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config/config.ini')
        ]
        
        for location in possible_locations:
            logger.info(f"尝试在备选位置查找配置文件: {location}")
            if os.path.exists(location):
                logger.info(f"找到配置文件: {location}")
                config_file = location
                break
        else:
            logger.error("无法找到配置文件")
            # 创建默认配置
            logger.info("创建默认配置")
            config = configparser.ConfigParser()
            config['general'] = {
                'nas_directories': '/data',
                'size_threshold': '100',
                'output_file': '/app/output/redundant_files',
                'schedule_time': '03:00',
                'ignore_links': 'true'
            }
            config['downloader'] = {'client_type': 'qbittorrent'}
            config['qbittorrent'] = {
                'host': '192.168.1.100',
                'port': '8080',
                'username': 'admin',
                'password': 'adminpassword'
            }
            config['transmission'] = {
                'host': '192.168.1.100',
                'port': '9091',
                'username': 'admin',
                'password': 'adminpassword'
            }
            return config
    
    # 加载配置文件
    config = configparser.ConfigParser()
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            logger.info(f"配置文件内容预览: {f.read(500)}...")
            f.seek(0)  # 重置文件指针
            config.read_file(f)
    except Exception as e:
        logger.error(f"读取配置文件出错: {str(e)}")
        # 创建默认配置
        logger.info("创建默认配置")
        config = configparser.ConfigParser()
        config['general'] = {
            'nas_directories': '/data',
            'size_threshold': '100',
            'output_file': '/app/output/redundant_files',
            'schedule_time': '03:00',
            'ignore_links': 'true'
        }
        config['downloader'] = {'client_type': 'qbittorrent'}
        config['qbittorrent'] = {
            'host': '192.168.1.100',
            'port': '8080',
            'username': 'admin',
            'password': 'adminpassword'
        }
        config['transmission'] = {
            'host': '192.168.1.100',
            'port': '9091',
            'username': 'admin',
            'password': 'adminpassword'
        }
        return config
    
    # 检查配置中是否包含必要的部分
    if 'general' not in config:
        logger.error("配置文件中缺少 'general' 部分")
        config['general'] = {
            'nas_directories': '/data',
            'size_threshold': '100',
            'output_file': '/app/output/redundant_files',
            'schedule_time': '03:00',
            'ignore_links': 'true'
        }
    
    # 处理路径映射配置
    if 'general' in config and 'path_mappings' in config['general']:
        path_mappings_str = config['general']['path_mappings']
        if path_mappings_str:
            logger.info(f"加载路径映射配置: {path_mappings_str}")
            try:
                # 解析路径映射配置
                path_mappings = {}
                mappings = [m.strip() for m in path_mappings_str.split(',')]
                for mapping in mappings:
                    if '=' in mapping:
                        container_path, nas_path = mapping.split('=', 1)
                        container_path = container_path.strip()
                        nas_path = nas_path.strip()
                        path_mappings[container_path] = nas_path
                        logger.info(f"路径映射: {container_path} -> {nas_path}")
                
                # 将路径映射添加到配置中
                config['path_mappings'] = path_mappings
            except Exception as e:
                logger.error(f"解析路径映射配置出错: {str(e)}")
                config['path_mappings'] = {}
        else:
            config['path_mappings'] = {}
    else:
        config['path_mappings'] = {}
    
    # 记录配置信息
    logger.info(f"配置文件加载成功: {config_file}")
    for section in config.sections():
        logger.info(f"配置部分: {section}")
        for key, value in config[section].items():
            if 'password' in key:
                logger.info(f"  {key}: ******")
            else:
                logger.info(f"  {key}: {value}")
    
    return config

# 应用路径映射，将下载器路径转换为NAS路径
def apply_path_mapping(file_path, path_mappings_str):
    if not path_mappings_str:
        return file_path
    
    # 规范化原始路径
    norm_path = os.path.normpath(file_path)
    original_norm_path = norm_path  # 保存原始规范化路径，用于调试
    
    # 解析映射配置
    path_mappings = {}
    try:
        # 处理多个路径映射配置
        for mapping in path_mappings_str.split(','):
            mapping = mapping.strip()
            if not mapping or '=' not in mapping:
                continue
                
            container_path, nas_path = mapping.split('=', 1)
            container_path = container_path.strip()
            nas_path = nas_path.strip()
            
            # 规范化路径，确保一致的格式
            container_path = os.path.normpath(container_path)
            nas_path = os.path.normpath(nas_path)
            
            path_mappings[container_path] = nas_path
    except Exception as e:
        logger.error(f"解析路径映射配置出错: {str(e)} - {path_mappings_str}")
        return file_path
    
    # 遍历所有映射规则尝试替换
    for container_path, nas_path in path_mappings.items():
        try:
            # 检查路径前缀
            if norm_path.startswith(container_path):
                # 替换路径前缀
                relative_path = os.path.relpath(norm_path, container_path)
                if relative_path == '.':  # 如果是完全匹配，没有相对路径
                    mapped_path = nas_path
                else:
                    mapped_path = os.path.join(nas_path, relative_path)
                
                logger.debug(f"路径映射: {norm_path} -> {mapped_path}")
                return mapped_path
            # 如果是根目录映射特殊处理
            elif container_path == '/' and norm_path.startswith('/'):
                mapped_path = os.path.join(nas_path, norm_path[1:])
                logger.debug(f"根目录映射: {norm_path} -> {mapped_path}")
                return mapped_path
        except Exception as e:
            logger.error(f"应用路径映射时出错: {str(e)} - 路径: {norm_path}, 映射: {container_path}={nas_path}")
    
    # 如果没有找到匹配的映射，返回原始路径
    return file_path

# 获取下载器中的做种文件列表
def get_seeding_files(config):
    if 'downloader' not in config:
        logger.error("配置文件中缺少 'downloader' 部分")
        return [], []
    
    seeding_files = []
    seeding_torrents = []  # 新增保存种子详细信息
    
    # 检查是否使用新版多下载器配置
    if 'enabled_clients' in config['downloader']:
        # 新版多下载器配置
        client_ids = [client_id.strip() for client_id in config['downloader']['enabled_clients'].split(',')]
        logger.info(f"使用多下载器配置，启用的下载器: {client_ids}")
        
        for client_id in client_ids:
            if client_id and client_id in config:
                client_config = config[client_id]
                client_type = client_config.get('type', '').lower()
                
                if client_type == 'qbittorrent':
                    logger.info(f"获取qBittorrent({client_id})做种文件")
                    client_files, client_torrents = get_qbittorrent_files_from_config(client_config, client_id)
                    logger.info(f"{client_id}做种文件数: {len(client_files)}")
                    seeding_files.extend(client_files)
                    seeding_torrents.extend(client_torrents)
                    
                elif client_type == 'transmission':
                    logger.info(f"获取Transmission({client_id})做种文件")
                    client_files, client_torrents = get_transmission_files_from_config(client_config, client_id)
                    logger.info(f"{client_id}做种文件数: {len(client_files)}")
                    seeding_files.extend(client_files)
                    seeding_torrents.extend(client_torrents)
                    
                else:
                    logger.warning(f"不支持的下载器类型: {client_type} (客户端 {client_id})")
            else:
                logger.warning(f"配置文件中缺少客户端配置: {client_id}")
    else:
        # 兼容旧版配置
        client_type = config['downloader'].get('client_type', '').lower()
        logger.info(f"使用旧版下载器配置，下载器类型: {client_type}")
        
        if client_type == 'qbittorrent':
            seeding_files, seeding_torrents = get_qbittorrent_files(config)
        elif client_type == 'transmission':
            seeding_files, seeding_torrents = get_transmission_files(config)
        elif client_type == 'both':
            # 同时获取两种下载器的做种文件
            qb_files, qb_torrents = get_qbittorrent_files(config)
            logger.info(f"qBittorrent做种文件数: {len(qb_files)}")
            
            tr_files, tr_torrents = get_transmission_files(config)
            logger.info(f"Transmission做种文件数: {len(tr_files)}")
            
            # 合并文件列表和种子信息
            seeding_files = qb_files + tr_files
            seeding_torrents = qb_torrents + tr_torrents
        else:
            logger.error(f"不支持的下载器类型: {client_type}")
    
    return seeding_files, seeding_torrents

# 从配置获取qBittorrent做种文件
def get_qbittorrent_files_from_config(client_config, client_id=''):
    host = client_config.get('host', '')
    port = client_config.get('port', '')
    username = client_config.get('username', '')
    password = client_config.get('password', '')
    
    # 获取此下载器的路径映射配置
    path_mappings_str = client_config.get('path_mappings', '')
    if path_mappings_str:
        logger.info(f"下载器 {client_id} 配置了路径映射: {path_mappings_str}")
    
    if not host or not port:
        logger.error(f"qBittorrent配置不完整，缺少host或port (客户端 {client_id})")
        return [], []
    
    base_url = f"http://{host}:{port}"
    session = requests.Session()
    
    try:
        # 登录
        login_url = f"{base_url}/api/v2/auth/login"
        logger.info(f"尝试登录qBittorrent: {login_url} (客户端 {client_id})")
        response = session.post(login_url, data={"username": username, "password": password})
        if response.status_code != 200:
            logger.error(f"登录qBittorrent失败: {response.text} (客户端 {client_id})")
            return [], []
        
        # 获取种子列表
        torrents_url = f"{base_url}/api/v2/torrents/info"
        logger.info(f"获取qBittorrent种子列表: {torrents_url} (客户端 {client_id})")
        response = session.get(torrents_url)
        if response.status_code != 200:
            logger.error(f"获取qBittorrent种子列表失败: {response.text} (客户端 {client_id})")
            return [], []
        
        torrents = response.json()
        logger.info(f"找到 {len(torrents)} 个qBittorrent种子 (客户端 {client_id})")
        seeding_files = []
        seeding_torrents = []
        
        # 仅处理正在做种和活动中的种子
        active_torrents = [t for t in torrents if t.get('state', '') in ['uploading', 'stalledUP', 'forcedUP', 'queuedUP', 'checkingUP']]
        logger.info(f"其中 {len(active_torrents)} 个正在做种 (客户端 {client_id})")
        
        # 用于去重的集合
        unique_paths = set()
        
        for torrent in active_torrents:
            # 获取种子的文件列表
            torrent_hash = torrent['hash']
            content_url = f"{base_url}/api/v2/torrents/files?hash={torrent_hash}"
            files_response = session.get(content_url)
            if files_response.status_code != 200:
                logger.warning(f"获取种子文件列表失败: {torrent_hash} (客户端 {client_id})")
                continue
            
            files = files_response.json()
            save_path = torrent.get('save_path', '')
            torrent_name = torrent.get('name', '')
            
            for file in files:
                file_name = file.get('name', '')
                file_path = os.path.normpath(os.path.join(save_path, file_name))
                file_size = file.get('size', 0)
                
                # 保存原始路径用于参考
                original_path = file_path
                
                # 应用路径映射
                mapped_file_path = apply_path_mapping(file_path, path_mappings_str)
                
                # 确保路径规范化
                mapped_file_path = os.path.normpath(mapped_file_path)
                
                # 记录映射前后的路径，便于调试
                if mapped_file_path != file_path:
                    logger.info(f"文件路径映射: {file_path} -> {mapped_file_path} (客户端 {client_id})")
                
                # 去重检查
                if mapped_file_path not in unique_paths:
                    unique_paths.add(mapped_file_path)
                    seeding_files.append(mapped_file_path)
                    
                    # 收集种子信息
                    seeding_torrents.append({
                        'file_path': mapped_file_path,
                        'original_path': original_path,  # 保存原始路径，用于调试
                        'file_name': os.path.basename(mapped_file_path),
                        'file_size': file_size,
                        'file_size_human': humanize.naturalsize(file_size, binary=True) if file_size else "未知",
                        'torrent_name': torrent_name,
                        'torrent_hash': torrent_hash,
                        'torrent_state': torrent.get('state', '未知'),
                        'save_path': save_path,
                        'client_type': 'qBittorrent',
                        'client_id': client_id,
                        'client_host': f"{host}:{port}",
                        'path_mapping': path_mappings_str  # 添加路径映射配置，便于排查
                    })
        
        logger.info(f"qBittorrent做种文件总数: {len(seeding_files)} (客户端 {client_id})")
        return seeding_files, seeding_torrents
    
    except Exception as e:
        logger.error(f"获取qBittorrent做种文件时出错: {str(e)} (客户端 {client_id})")
        import traceback
        logger.error(traceback.format_exc())
        return [], []

# 从配置获取Transmission做种文件
def get_transmission_files_from_config(client_config, client_id=''):
    host = client_config.get('host', '')
    port = client_config.get('port', '')
    username = client_config.get('username', '')
    password = client_config.get('password', '')
    
    # 获取此下载器的路径映射配置
    path_mappings_str = client_config.get('path_mappings', '')
    if path_mappings_str:
        logger.info(f"下载器 {client_id} 配置了路径映射: {path_mappings_str}")
    
    if not host or not port:
        logger.error(f"Transmission配置不完整，缺少host或port (客户端 {client_id})")
        return [], []
    
    url = f"http://{host}:{port}/transmission/rpc"
    session = requests.Session()
    
    try:
        # 获取X-Transmission-Session-Id
        logger.info(f"尝试连接Transmission: {url} (客户端 {client_id})")
        response = session.get(url, auth=(username, password))
        if response.status_code == 409:
            session_id = response.headers.get('X-Transmission-Session-Id')
            headers = {'X-Transmission-Session-Id': session_id}
        else:
            logger.error(f"获取Transmission会话ID失败: {response.status_code} (客户端 {client_id})")
            return [], []
        
        # 获取所有种子信息
        payload = {
            "method": "torrent-get",
            "arguments": {
                "fields": ["id", "name", "downloadDir", "files", "hashString", "totalSize", "status", "percentDone"]
            }
        }
        
        logger.info(f"获取Transmission种子列表 (客户端 {client_id})")
        response = session.post(url, json=payload, headers=headers, auth=(username, password))
        if response.status_code != 200:
            logger.error(f"获取Transmission种子列表失败: {response.text} (客户端 {client_id})")
            return [], []
        
        data = response.json()
        torrents = data.get('arguments', {}).get('torrents', [])
        logger.info(f"找到 {len(torrents)} 个Transmission种子 (客户端 {client_id})")
        seeding_files = []
        seeding_torrents = []
        
        # 仅处理完成下载并正在做种的种子（状态6=正在做种，百分比100%=已完成）
        active_torrents = [t for t in torrents if t.get('percentDone', 0) == 1 and t.get('status', 0) == 6]
        logger.info(f"其中 {len(active_torrents)} 个正在做种 (客户端 {client_id})")
        
        # 用于去重的集合
        unique_paths = set()
        
        for torrent in active_torrents:
            download_dir = torrent.get('downloadDir', '')
            files = torrent.get('files', [])
            torrent_name = torrent.get('name', '')
            torrent_hash = torrent.get('hashString', '')
            torrent_size = torrent.get('totalSize', 0)
            
            for file in files:
                file_name = file.get('name', '')
                file_path = os.path.normpath(os.path.join(download_dir, file_name))
                file_size = file.get('length', 0)
                
                # 保存原始路径用于参考
                original_path = file_path
                
                # 应用路径映射
                mapped_file_path = apply_path_mapping(file_path, path_mappings_str)
                
                # 确保路径规范化
                mapped_file_path = os.path.normpath(mapped_file_path)
                
                # 记录映射前后的路径，便于调试
                if mapped_file_path != file_path:
                    logger.info(f"文件路径映射: {file_path} -> {mapped_file_path} (客户端 {client_id})")
                
                # 去重检查
                if mapped_file_path not in unique_paths:
                    unique_paths.add(mapped_file_path)
                    seeding_files.append(mapped_file_path)
                    
                    # 收集种子信息
                    seeding_torrents.append({
                        'file_path': mapped_file_path,
                        'original_path': original_path,  # 保存原始路径，用于调试
                        'file_name': os.path.basename(mapped_file_path),
                        'file_size': file_size,
                        'file_size_human': humanize.naturalsize(file_size, binary=True) if file_size else "未知",
                        'torrent_name': torrent_name,
                        'torrent_hash': torrent_hash,
                        'torrent_state': '做种中',
                        'save_path': download_dir,
                        'client_type': 'Transmission',
                        'client_id': client_id,
                        'client_host': f"{host}:{port}",
                        'path_mapping': path_mappings_str  # 添加路径映射配置，便于排查
                    })
        
        logger.info(f"Transmission做种文件总数: {len(seeding_files)} (客户端 {client_id})")
        return seeding_files, seeding_torrents
    
    except Exception as e:
        logger.error(f"获取Transmission做种文件时出错: {str(e)} (客户端 {client_id})")
        import traceback
        logger.error(traceback.format_exc())
        return [], []

# 获取qBittorrent做种文件 (旧版兼容)
def get_qbittorrent_files(config):
    if 'qbittorrent' not in config:
        logger.error("配置文件中缺少 'qbittorrent' 部分")
        return [], []
    
    return get_qbittorrent_files_from_config(config['qbittorrent'])

# 获取Transmission做种文件 (旧版兼容)
def get_transmission_files(config):
    if 'transmission' not in config:
        logger.error("配置文件中缺少 'transmission' 部分")
        return [], []
    
    return get_transmission_files_from_config(config['transmission'])

# 获取文件详细信息
def get_file_details(file_path):
    try:
        file_stat = os.stat(file_path)
        size_bytes = file_stat.st_size
        size_human = humanize.naturalsize(size_bytes, binary=True)
        
        # 获取创建和修改时间
        ctime = datetime.fromtimestamp(file_stat.st_ctime)
        mtime = datetime.fromtimestamp(file_stat.st_mtime)
        
        # 计算文件类型
        file_type = "未知"
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.m2ts':
            file_type = "蓝光原盘"
        elif ext in ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'):
            file_type = "视频"
        elif ext in ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'):
            file_type = "音频"
        elif ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'):
            file_type = "图片"
        elif ext in ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'):
            file_type = "文档"
        
        # 返回详细信息字典
        return {
            'size_bytes': size_bytes,
            'size_human': size_human,
            'create_time': ctime.strftime('%Y-%m-%d %H:%M:%S'),
            'modify_time': mtime.strftime('%Y-%m-%d %H:%M:%S'),
            'file_type': file_type,
            'extension': ext[1:] if ext else ""
        }
    except Exception as e:
        logger.warning(f"无法获取文件详细信息: {file_path}, 错误: {str(e)}")
        return {
            'size_bytes': 0,
            'size_human': "未知",
            'create_time': "未知",
            'modify_time': "未知",
            'file_type': "未知",
            'extension': "未知"
        }

# 获取指定目录下的所有文件
def get_nas_files(directory, size_threshold, exclude_dirs=None, ignore_links=True):
    try:
        if not os.path.exists(directory):
            logger.error(f"目录不存在: {directory}")
            return [], 0, 0, 0
        
        # 初始化排除目录列表
        if exclude_dirs is None:
            exclude_dirs = []
        
        # 规范化排除目录路径
        norm_exclude_dirs = [os.path.normpath(d) for d in exclude_dirs]
        
        nas_files = []
        size_threshold_bytes = size_threshold * 1024 * 1024  # 转换为字节
        logger.info(f"开始扫描NAS目录: {directory}，大小阈值: {size_threshold}MB，忽略链接: {ignore_links}")
        logger.info(f"排除目录: {norm_exclude_dirs}")
        
        # 记录符号链接相关信息
        symlink_count = 0
        hardlink_count = 0
        normal_file_count = 0
        error_count = 0
        excluded_count = 0
        
        for root, _, files in os.walk(directory, followlinks=True):
            # 检查是否为符号链接目录
            is_symlink_dir = os.path.islink(root)
            if is_symlink_dir:
                logger.info(f"发现符号链接目录: {root} -> {os.path.realpath(root)}")
            
            # 检查当前目录是否应该被排除
            norm_root = os.path.normpath(root)
            should_exclude = False
            for exclude_dir in norm_exclude_dirs:
                if norm_root == exclude_dir or norm_root.startswith(exclude_dir + os.sep):
                    logger.debug(f"排除目录: {norm_root} (匹配规则: {exclude_dir})")
                    should_exclude = True
                    excluded_count += len(files)
                    break
            
            if should_exclude:
                continue
            
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # 检查是否为符号链接或硬链接
                    if os.path.islink(file_path):
                        symlink_count += 1
                        logger.debug(f"跳过软链接文件: {file_path} -> {os.path.realpath(file_path)}")
                        # 如果配置为忽略链接，则跳过
                        if ignore_links:
                            continue
                    else:
                        # 检查是否为硬链接(st_nlink > 1)
                        stat_info = os.stat(file_path)
                        if stat_info.st_nlink > 1:
                            hardlink_count += 1
                            logger.debug(f"检测到硬链接文件: {file_path}, 链接数: {stat_info.st_nlink}")
                            # 如果配置为忽略链接，则跳过
                            if ignore_links:
                                continue
                    
                    # 获取文件大小
                    file_size = os.path.getsize(file_path)
                    if file_size >= size_threshold_bytes:
                        file_details = get_file_details(file_path)
                        nas_files.append((file_path, file_details))
                        normal_file_count += 1
                except Exception as e:
                    logger.warning(f"无法处理文件: {file_path}, 错误: {str(e)}")
                    error_count += 1
        
        logger.info(f"扫描完成: 找到 {len(nas_files)} 个普通文件, {symlink_count} 个软链接, "
                   f"{hardlink_count} 个硬链接, 排除了 {excluded_count} 个文件, 遇到 {error_count} 个错误")
        return nas_files, symlink_count, hardlink_count, error_count
    
    except Exception as e:
        logger.error(f"扫描NAS文件时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return [], 0, 0, 0

# 获取多个NAS目录下的所有文件
def get_all_nas_files(config):
    try:
        # 获取目录列表
        size_threshold = int(config['general'].get('size_threshold', 100))
        ignore_links = config['general'].get('ignore_links', 'true').lower() in ('true', 'yes', '1', 'on')
        
        # 获取排除目录
        exclude_dirs_str = config['general'].get('exclude_directories', '')
        if exclude_dirs_str:
            # 支持中英文逗号分隔
            exclude_dirs_str = exclude_dirs_str.replace('，', ',')
            if ',' in exclude_dirs_str:
                exclude_dirs = [d.strip() for d in exclude_dirs_str.split(',') if d.strip()]
            else:
                exclude_dirs = [exclude_dirs_str.strip()]
            logger.info(f"配置了以下排除目录: {exclude_dirs}")
        else:
            exclude_dirs = []
            logger.info("未配置排除目录")
        
        # 检查是否使用旧的配置格式还是新的格式
        if 'nas_directory' in config['general']:
            # 兼容旧格式
            directory_str = config['general']['nas_directory']
            logger.info(f"使用旧配置项 'nas_directory': {directory_str}")
        elif 'nas_directories' in config['general']:
            # 新格式
            directory_str = config['general']['nas_directories']
            logger.info(f"使用配置项 'nas_directories': {directory_str}")
        else:
            logger.error("配置文件中缺少 'nas_directories' 或 'nas_directory' 配置")
            return []
        
        # 解析目录列表，支持中英文逗号分隔的多个目录
        directory_str = directory_str.replace('，', ',')
        if ',' in directory_str:
            directories = [d.strip() for d in directory_str.split(',') if d.strip()]
        else:
            directories = [directory_str.strip()]
        
        logger.info(f"需要扫描的目录列表: {directories}")
        logger.info(f"是否忽略链接文件: {ignore_links}")
        
        # 扫描所有目录并合并文件列表
        all_files = []
        total_symlinks = 0
        total_hardlinks = 0
        total_errors = 0
        
        for directory in directories:
            if directory:  # 确保目录不为空
                files, symlinks, hardlinks, errors = get_nas_files(directory, size_threshold, exclude_dirs, ignore_links)
                logger.info(f"目录 {directory} 中找到 {len(files)} 个文件, {symlinks} 个软链接, {hardlinks} 个硬链接")
                all_files.extend(files)
                total_symlinks += symlinks
                total_hardlinks += hardlinks
                total_errors += errors
        
        # 去重 (基于文件路径)
        unique_paths = set()
        unique_files = []
        for file_path, details in all_files:
            norm_path = os.path.normpath(file_path)
            if norm_path not in unique_paths:
                unique_paths.add(norm_path)
                unique_files.append((file_path, details))
        
        logger.info(f"所有目录共找到 {len(unique_files)} 个不重复文件, 共 {total_symlinks} 个软链接, {total_hardlinks} 个硬链接")
        
        return unique_files
        
    except Exception as e:
        logger.error(f"扫描多个NAS目录时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

# 找出没有做种的冗余文件
def find_redundant_files(nas_files, seeding_files):
    # 规范化路径以便比较
    seeding_files_normalized = [os.path.normpath(f) for f in seeding_files]
    
    # 找出在NAS文件列表中但不在做种文件列表中的文件
    redundant_files = []
    for file_path, details in nas_files:
        norm_path = os.path.normpath(file_path)
        if norm_path not in seeding_files_normalized:
            redundant_files.append((file_path, details))
    
    return redundant_files

# 找出正在做种但已被删除的文件
def find_missing_seeding_files(seeding_files, seeding_torrents):
    missing_files = []
    processed_paths = set()  # 用于去重
    
    # 获取配置中的NAS目录
    config = load_config()
    nas_dirs = []
    if 'general' in config and 'nas_directories' in config['general']:
        dirs_str = config['general']['nas_directories']
        # 支持中英文逗号
        dirs_str = dirs_str.replace('，', ',')
        nas_dirs = [os.path.normpath(d.strip()) for d in dirs_str.split(',') if d.strip()]
        logger.info(f"配置的NAS目录: {nas_dirs}")
    
    for i, file_path in enumerate(seeding_files):
        # 规范化路径
        norm_path = os.path.normpath(file_path)
        
        # 如果已经处理过此路径，则跳过
        if norm_path in processed_paths:
            continue
        processed_paths.add(norm_path)
        
        # 检查文件是否在配置的NAS目录中
        in_nas_dirs = False
        for nas_dir in nas_dirs:
            if norm_path.startswith(nas_dir):
                in_nas_dirs = True
                break
        
        # 如果文件不在配置的NAS目录中，跳过检查
        if not in_nas_dirs:
            logger.info(f"跳过检查非NAS目录文件: {norm_path}")
            continue
        
        # 检查文件是否存在
        if not os.path.exists(norm_path) or not os.path.isfile(norm_path):
            try:
                # 获取种子信息
                if i < len(seeding_torrents):  # 确保有对应的种子信息
                    torrent_info = seeding_torrents[i]
                    
                    # 标记为确实丢失，而不是路径问题
                    is_real_missing = True
                    
                    # 获取原始路径(下载器内路径)，用于额外检查
                    original_path = torrent_info.get('original_path', '')
                    
                    # 获取客户端ID和路径映射，用于详细日志
                    client_id = torrent_info.get('client_id', '')
                    path_mapping = torrent_info.get('path_mapping', '')
                    
                    logger.info(f"检测到可能丢失的文件: {norm_path} (原始路径: {original_path}, 客户端: {client_id})")
                    if path_mapping:
                        logger.info(f"使用的路径映射: {path_mapping}")
                    
                    # 额外检查，确认文件确实不存在（解决路径格式差异问题）
                    alt_paths = [
                        # 尝试替换斜杠
                        norm_path.replace('\\', '/'),
                        norm_path.replace('/', '\\'),
                        # 尝试去除特殊字符
                        os.path.normpath(re.sub(r'[^a-zA-Z0-9/\\._\-]', '_', file_path)),
                        # 尝试按目录单独查找
                        os.path.join(torrent_info['save_path'], torrent_info['file_name']),
                        # 如果有原始路径，也尝试检查
                        original_path
                    ]
                    
                    # 检查替代路径是否存在
                    for alt_path in alt_paths:
                        if not alt_path:
                            continue
                        alt_norm_path = os.path.normpath(alt_path)
                        if alt_norm_path != norm_path and alt_norm_path not in processed_paths:
                            processed_paths.add(alt_norm_path)  # 添加到已处理路径
                            if os.path.exists(alt_path) and os.path.isfile(alt_path):
                                logger.info(f"文件通过替代路径找到: {alt_path} (原路径: {norm_path})")
                                is_real_missing = False
                                break
                    
                    if is_real_missing:
                        logger.info(f"确认丢失的文件: {norm_path}")
                        # 防止重复添加相同路径
                        duplicate = False
                        for existing in missing_files:
                            if existing['file_path'] == torrent_info['file_path']:
                                duplicate = True
                                break
                        if not duplicate:
                            missing_files.append(torrent_info)
                else:
                    # 没有种子信息时的备用处理
                    filename = os.path.basename(norm_path)
                    directory = os.path.dirname(norm_path)
                    extension = os.path.splitext(filename)[1][1:] if os.path.splitext(filename)[1] else ""
                    
                    # 检查是否重复
                    duplicate = False
                    for existing in missing_files:
                        if existing.get('file_path') == norm_path:
                            duplicate = True
                            break
                    
                    if not duplicate:
                        missing_files.append({
                            'file_path': norm_path,
                            'file_name': filename,
                            'file_size': 0,
                            'file_size_human': "未知",
                            'torrent_name': "未知",
                            'torrent_hash': "未知",
                            'torrent_state': "未知",
                            'save_path': directory,
                            'client_type': "未知",
                            'client_id': "",
                            'client_host': "",
                            'extension': extension
                        })
            except Exception as e:
                logger.warning(f"处理缺失文件时出错: {norm_path}, 错误: {str(e)}")
                import traceback
                logger.warning(traceback.format_exc())
    
    return missing_files

# 格式化输出文件
def format_output(redundant_files, nas_files_count, seeding_files_count):
    output = []
    
    # 标题
    output.append("=" * 80)
    output.append("                       NAS 冗余文件检查报告                           ")
    output.append("=" * 80)
    
    # 基本信息
    output.append(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append(f"总NAS文件数: {nas_files_count}")
    output.append(f"做种文件数: {seeding_files_count}")
    output.append(f"冗余文件数: {len(redundant_files)}")
    output.append("-" * 80)
    
    # 汇总信息
    total_size = sum(details['size_bytes'] for _, details in redundant_files)
    output.append(f"冗余文件总大小: {humanize.naturalsize(total_size, binary=True)}")
    
    # 按文件类型汇总
    file_types = {}
    for _, details in redundant_files:
        file_type = details['file_type']
        if file_type in file_types:
            file_types[file_type] += 1
        else:
            file_types[file_type] = 1
    
    output.append("\n文件类型统计:")
    for file_type, count in file_types.items():
        output.append(f"  {file_type}: {count} 个文件")
    
    # 冗余文件列表
    output.append("\n" + "=" * 80)
    output.append("冗余文件列表:")
    output.append("-" * 80)
    
    # 文件列表
    for i, (file_path, details) in enumerate(redundant_files, 1):
        # 获取文件名和目录
        filename = os.path.basename(file_path)
        directory = os.path.dirname(file_path)
        
        output.append(f"[{i}] {filename}")
        output.append(f"    路径: {directory}")
        output.append(f"    大小: {details['size_human']} | 类型: {details['file_type']} | 扩展名: {details['extension']}")
        output.append(f"    创建时间: {details['create_time']} | 修改时间: {details['modify_time']}")
        output.append("-" * 80)
    
    return "\n".join(output)

# 格式化已删除的做种文件输出
def format_missing_seeding_output(missing_files):
    if not missing_files:
        return "未发现正在做种但已删除的文件。"
    
    output = []
    
    # 标题
    output.append("=" * 80)
    output.append("                正在做种但已删除的文件列表                           ")
    output.append("=" * 80)
    
    # 基本信息
    output.append(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append(f"已删除文件数: {len(missing_files)}")
    output.append("-" * 80)
    output.append("注意：此列表只包含配置的NAS目录中丢失的文件，不包含未配置监控的目录")
    
    # 总计大小
    total_size = sum(file.get('file_size', 0) for file in missing_files)
    output.append(f"总文件大小: {humanize.naturalsize(total_size, binary=True)}")
    
    # 按下载器类型分组统计
    client_stats = {}
    for file in missing_files:
        client = file.get('client_type', "未知")
        if client in client_stats:
            client_stats[client] += 1
        else:
            client_stats[client] = 1
    
    output.append("\n下载器统计:")
    for client, count in client_stats.items():
        output.append(f"  {client}: {count} 个文件")
    
    # 按种子状态分组统计
    state_stats = {}
    for file in missing_files:
        state = file.get('torrent_state', "未知")
        if state in state_stats:
            state_stats[state] += 1
        else:
            state_stats[state] = 1
    
    output.append("\n种子状态统计:")
    for state, count in state_stats.items():
        output.append(f"  {state}: {count} 个文件")
    
    # 按文件类型统计
    ext_stats = {}
    for file in missing_files:
        ext = file.get('extension', file.get('file_path', "").split('.')[-1] if '.' in file.get('file_path', "") else "").lower()
        if ext in ext_stats:
            ext_stats[ext] += 1
        else:
            ext_stats[ext] = 1
    
    output.append("\n文件类型统计:")
    for ext, count in ext_stats.items():
        ext_display = ext if ext else "无扩展名"
        output.append(f"  {ext_display}: {count} 个文件")
    
    # 已删除的做种文件列表
    output.append("\n" + "=" * 80)
    output.append("已删除的做种文件详细列表:")
    output.append("-" * 80)
    
    # 文件列表
    for i, file in enumerate(missing_files, 1):
        output.append(f"[{i}] {file.get('file_name', os.path.basename(file.get('file_path', 'Unknown')))}")
        output.append(f"    文件路径: {file.get('file_path', '未知')}")
        output.append(f"    保存位置: {file.get('save_path', '未知')}")
        output.append(f"    文件大小: {file.get('file_size_human', '未知')}")
        
        # 种子信息
        torrent_name = file.get('torrent_name', '未知')
        torrent_hash = file.get('torrent_hash', '未知')
        torrent_state = file.get('torrent_state', '未知')
        output.append(f"    种子名称: {torrent_name}")
        output.append(f"    种子状态: {torrent_state}")
        output.append(f"    种子哈希: {torrent_hash[:8]}{'...' if len(torrent_hash) > 8 else ''}")
        
        # 下载器信息
        client_type = file.get('client_type', '未知')
        client_id = file.get('client_id', '')
        client_host = file.get('client_host', '未知')
        output.append(f"    下载器: {client_type}{f' ({client_id})' if client_id else ''} - {client_host}")
        
        output.append("-" * 80)
    
    return "\n".join(output)

# 执行检查
def run_check():
    logger.info("开始检查冗余文件...")
    
    config = load_config()
    output_file_prefix = config['general'].get('output_file', 'redundant_files')
    
    # 如果output_file_prefix没有指定路径，添加默认的/app/output路径前缀
    if output_file_prefix and not os.path.isabs(output_file_prefix) and '/' not in output_file_prefix and '\\' not in output_file_prefix:
        output_file_prefix = os.path.join('/app/output', output_file_prefix)
        logger.info(f"未指定输出路径，使用默认路径：{output_file_prefix}")
    
    # 获取做种文件
    seeding_files, seeding_torrents = get_seeding_files(config)
    logger.info(f"找到 {len(seeding_files)} 个做种文件")
    
    # 获取NAS文件 - 使用新的多目录支持函数
    nas_files = get_all_nas_files(config)
    size_threshold = int(config['general'].get('size_threshold', 100))
    logger.info(f"找到 {len(nas_files)} 个NAS文件 (大于 {size_threshold}MB)")
    
    # 找出冗余文件
    redundant_files = find_redundant_files(nas_files, seeding_files)
    logger.info(f"找到 {len(redundant_files)} 个冗余文件")
    
    # 找出正在做种但已删除的文件
    missing_files = find_missing_seeding_files(seeding_files, seeding_torrents)
    logger.info(f"找到 {len(missing_files)} 个正在做种但已删除的文件")
    
    # 设置时间戳和输出路径
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 确保输出目录存在
    try:
        # 如果用户在配置中指定了前缀，使用用户配置
        if output_file_prefix:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file_prefix)
            try:
                if output_dir and not os.path.exists(output_dir):
                    logger.info(f"创建配置的输出目录: {output_dir}/")
                    os.makedirs(output_dir, exist_ok=True)
                
                # 使用用户配置的前缀
                redundant_output_path = f"{output_file_prefix}_{timestamp}.txt"
                if "redundant_files" in output_file_prefix:
                    missing_output_path = redundant_output_path.replace("redundant_files", "missing_files")
                else:
                    missing_output_path = f"{output_file_prefix}_missing_{timestamp}.txt"
            except Exception as e:
                logger.error(f"处理输出路径时出错: {str(e)}")
                # 如果创建目录失败，使用默认备选路径
                redundant_output_path = f"/app/output/redundant_files_{timestamp}.txt"
                missing_output_path = f"/app/output/missing_files_{timestamp}.txt"
                logger.info(f"将使用备选路径: {redundant_output_path} 和 {missing_output_path}")
                # 确保备选目录存在
                os.makedirs("/app/output", exist_ok=True)
        else:
            # 如果用户未指定前缀，使用默认路径
            redundant_output_path = f"/app/output/redundant_files_{timestamp}.txt"
            missing_output_path = f"/app/output/missing_files_{timestamp}.txt"
            logger.info(f"未配置输出文件前缀，使用默认路径: {redundant_output_path} 和 {missing_output_path}")
            # 确保输出目录存在
            os.makedirs("/app/output", exist_ok=True)
        
        logger.info(f"将保存冗余文件结果到: {redundant_output_path}")
        logger.info(f"将保存已删除做种文件结果到: {missing_output_path}")
    
    except Exception as e:
        logger.error(f"创建输出目录时出错: {str(e)}")
        # 使用备选位置
        try:
            os.makedirs("/app/output", exist_ok=True)
            redundant_output_path = f"/app/output/redundant_files_{timestamp}.txt"
            missing_output_path = f"/app/output/missing_files_{timestamp}.txt"
        except:
            # 如果创建本地output目录也失败，则使用app目录
            redundant_output_path = f"/app/output/redundant_files_{timestamp}.txt"
            missing_output_path = f"/app/output/missing_files_{timestamp}.txt"
            # 确保/app/output目录存在
            os.makedirs("/app/output", exist_ok=True)
        logger.info(f"将使用备选路径: {redundant_output_path} 和 {missing_output_path}")
    
    # 格式化输出内容
    output_content = format_output(redundant_files, len(nas_files), len(seeding_files))
    missing_output_content = format_missing_seeding_output(missing_files)
    
    try:
        # 保存冗余文件报告
        with open(redundant_output_path, 'w', encoding='utf-8') as f:
            f.write(output_content)
        logger.info(f"冗余文件列表已保存到: {redundant_output_path}")
        
        # 保存缺失文件报告
        with open(missing_output_path, 'w', encoding='utf-8') as f:
            f.write(missing_output_content)
        logger.info(f"已删除做种文件列表已保存到: {missing_output_path}")
        
    except Exception as e:
        logger.error(f"保存结果文件时出错: {str(e)}")
        # 尝试使用另一个位置
        try:
            # 确保备选目录存在
            os.makedirs("/app/output", exist_ok=True)
            alt_path = f"/app/output/redundant_files_{timestamp}.txt"
            alt_missing_path = f"/app/output/missing_files_{timestamp}.txt"
            
            logger.info(f"尝试保存到备选位置: {alt_path} 和 {alt_missing_path}")
            
            with open(alt_path, 'w', encoding='utf-8') as f:
                f.write(output_content)
            
            with open(alt_missing_path, 'w', encoding='utf-8') as f:
                f.write(missing_output_content)
            
            logger.info(f"报告已保存到备选位置: {alt_path} 和 {alt_missing_path}")
        except Exception as e2:
            logger.error(f"保存到备选位置也失败: {str(e2)}")
            logger.info("直接打印结果:")
            logger.info(output_content)
            logger.info(missing_output_content)

# 主函数
def main():
    parser = argparse.ArgumentParser(description='检查NAS中未做种的冗余文件')
    parser.add_argument('--now', action='store_true', help='立即执行检查')
    parser.add_argument('--config', default='config.ini', help='配置文件路径')
    args = parser.parse_args()
    
    try:
        # 加载配置
        logger.info(f"使用配置文件: {args.config}")
        config = load_config(args.config)
        
        # 确保 general 部分存在
        if 'general' not in config:
            logger.error("配置文件中缺少 'general' 部分，使用默认值")
            config['general'] = {
                'nas_directories': '/data',
                'size_threshold': '100',
                'output_file': '/app/output/redundant_files',
                'schedule_time': '03:00',
                'ignore_links': 'true'
            }
            
        # 确保output_file配置使用有效路径
        if 'output_file' in config['general']:
            output_file = config['general']['output_file']
            if output_file and not os.path.isabs(output_file) and '/' not in output_file and '\\' not in output_file:
                # 如果是简单文件名，添加/app/output路径
                config['general']['output_file'] = os.path.join('/app/output', output_file)
                logger.info(f"将输出文件路径设置为: {config['general']['output_file']}")
            
        schedule_time = config['general'].get('schedule_time', '03:00')
        logger.info(f"计划任务时间: {schedule_time}")
        
        # 设置定时任务
        schedule.every().day.at(schedule_time).do(run_check)
        logger.info(f"已设置每日 {schedule_time} 执行检查")
        
        # 无论--now参数是否指定，都立即执行一次检查
        logger.info("程序启动，立即执行检查...")
        run_check()
        
        # 保持程序运行
        logger.info("进入主循环，等待执行计划任务...")
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 