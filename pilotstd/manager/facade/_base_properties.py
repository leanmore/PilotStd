# pilotstd/manager/facade/_base_properties.py
# 兼容旧代码的属性代理混入 — 从 _base.py 提取
# 所有 @property 将 BaseFacade 的属性访问委托到 self._core 或自身实例变量

from __future__ import annotations


class _BasePropertiesMixin:
    """兼容旧代码的属性代理集合（混入 BaseFacade）。"""

    # ===== 核心组件属性代理 =====

    @property
    def cfg(self):
        return self._core.cfg

    @property
    def db(self):
        return self._core.db

    @property
    def parser(self):
        return self._core.parser

    @property
    def scanner(self):
        return self._core.scanner

    @property
    def query_engine(self):
        return self._core.query_engine

    @query_engine.setter
    def query_engine(self, value):
        self._core.query_engine = value

    @property
    def cache(self):
        return self._core.cache

    @property
    def quota_tracker(self):
        return self._core.quota_tracker

    @property
    def adapter_manager(self):
        return self._core.adapter_manager

    @property
    def file_index(self):
        return self._core.file_index

    @property
    def download_engine(self):
        return self._core.download_engine

    @download_engine.setter
    def download_engine(self, value):
        self._core.download_engine = value

    @property
    def router(self):
        return self._core.router

    @property
    def task_queue(self):
        return self._core.task_queue

    @property
    def _query_adapters(self):
        return self._core._query_adapters

    @property
    def notification_mgr(self):
        return self._core.notification_mgr

    @property
    def validity_checker(self):
        return self._core.validity_checker

    @property
    def _announce_svc(self):
        return self._core.announce_svc

    @_announce_svc.setter
    def _announce_svc(self, value):
        self._core.announce_svc = value

    @property
    def _organizer_svc(self):
        return self._core.organizer_svc

    @property
    def _pending_svc(self):
        return self._core.pending_svc

    @_pending_svc.setter
    def _pending_svc(self, value):
        self._core.pending_svc = value

    @property
    def validity_service(self):
        return self._validity_service

    @property
    def user_service(self):
        return self._user_service

    @property
    def _scheduled_svc(self):
        return self._core.scheduled_svc

    @_scheduled_svc.setter
    def _scheduled_svc(self, value):
        self._core.scheduled_svc = value

    @property
    def _classifier(self):
        return self._core.classifier

    @_classifier.setter
    def _classifier(self, value):
        self._core.classifier = value

    # ===== 运行时状态列表的属性代理 =====

    @property
    def _parsed_results(self):
        return self._core.parsed_results

    @_parsed_results.setter
    def _parsed_results(self, value):
        self._core.parsed_results = value

    @property
    def _queried_items(self):
        return self._core.queried_items

    @_queried_items.setter
    def _queried_items(self, value):
        self._core.queried_items = value

    @property
    def _query_results(self):
        return self._core.query_results

    @_query_results.setter
    def _query_results(self, value):
        self._core.query_results = value

    @property
    def _download_list(self):
        return self._core.download_list

    @_download_list.setter
    def _download_list(self, value):
        self._core.download_list = value

    @property
    def _expire_list(self):
        return self._core.expire_list

    @_expire_list.setter
    def _expire_list(self, value):
        self._core.expire_list = value

    @property
    def _pending_list(self):
        return self._core.pending_list

    @_pending_list.setter
    def _pending_list(self, value):
        self._core.pending_list = value

    @property
    def _download_tasks(self):
        return self._core.download_tasks

    @_download_tasks.setter
    def _download_tasks(self, value):
        self._core.download_tasks = value

    @property
    def _last_skipped_dirs(self):
        return self._core.last_skipped_dirs

    @_last_skipped_dirs.setter
    def _last_skipped_dirs(self, value):
        self._core.last_skipped_dirs = value

    @property
    def _file_watcher(self):
        return self._core._file_watcher

    @_file_watcher.setter
    def _file_watcher(self, value):
        self._core._file_watcher = value
