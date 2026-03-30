"""
@FileName: long_term_memory.py
@Description: 长期记忆 - 向量数据库 + 持久化
@Author: HiPeng
@Github: https://github.com/neopen/video-shot-agent
@Time: 2026/3/30 13:09
"""
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


class LongTermMemory:
    """长期记忆 - 基于向量数据库，支持持久化和元数据过滤"""

    def __init__(self, embeddings: Embeddings, collection_name: str = "penshot_memory",
        persist_directory: Optional[str] = "data/output/memory"):
        """
        初始化长期记忆

        Args:
            collection_name: 集合名称
            persist_directory: 持久化目录
        """
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.collection_name = collection_name
        self.persist_directory = persist_directory

        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory
        )

        # 记忆统计
        self._stats = {
            "total_stored": 0,
            "last_cleanup": None
        }

    def store(self, text: str, metadata: Dict[str, Any]) -> str:
        """存储长期记忆，返回记忆ID"""
        # 生成唯一ID
        memory_id = hashlib.md5(
            f"{text}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # 添加时间戳
        metadata.update({
            "memory_id": memory_id,
            "stored_at": datetime.now().isoformat(),
            "text_length": len(text)
        })

        self.vectorstore.add_texts(
            texts=[text],
            metadatas=[metadata],
            ids=[memory_id]
        )

        self._stats["total_stored"] += 1
        return memory_id

    def store_batch(self, texts: List[str], metadatas: List[Dict[str, Any]]) -> List[str]:
        """批量存储记忆"""
        memory_ids = []
        for text, metadata in zip(texts, metadatas):
            memory_id = self.store(text, metadata)
            memory_ids.append(memory_id)
        return memory_ids

    def retrieve(self, query: str, k: int = 3, score_threshold: float = 0.0) -> List[Dict]:
        """检索相关记忆"""
        results = self.vectorstore.similarity_search_with_score(
            query, k=k
        )
        return [
            {
                "content": doc.page_content,
                "score": score,
                "metadata": doc.metadata,
                "memory_id": doc.metadata.get("memory_id")
            }
            for doc, score in results
            if score >= score_threshold
        ]

    def retrieve_by_filter(self, query: str, filter_dict: Dict[str, Any], k: int = 3) -> List[Document]:
        """按条件过滤检索"""
        results = self.vectorstore.similarity_search(
            query, k=k, filter=filter_dict
        )
        return results

    def retrieve_by_type(self, memory_type: str, query: str, k: int = 3) -> List[Document]:
        """按类型检索记忆"""
        return self.retrieve_by_filter(query, {"type": memory_type}, k)

    def get_by_id(self, memory_id: str) -> Optional[Document]:
        """根据ID获取记忆"""
        # Chroma 不直接支持按ID查询，需要遍历
        # 这里返回 None，实际可考虑其他实现
        return None

    def delete_by_filter(self, filter_dict: Dict[str, Any]) -> int:
        """按条件删除记忆"""
        # Chroma 删除需要先查询再删除
        try:
            # 获取所有匹配的文档
            results = self.vectorstore.get(where=filter_dict)
            ids = results.get("ids", [])
            if ids:
                self.vectorstore.delete(ids)
                self._stats["total_stored"] -= len(ids)
                return len(ids)
        except Exception:
            pass
        return 0

    def delete_old_memories(self, days: int = 30) -> int:
        """删除超过指定天数的记忆"""
        cutoff = datetime.now().timestamp() - (days * 24 * 3600)
        # 简化实现，实际需要根据 metadata 中的时间过滤
        return 0

    def clear_all(self) -> None:
        """清空所有记忆"""
        try:
            self.vectorstore.delete_collection()
            self.vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            self._stats["total_stored"] = 0
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_stored": self._stats["total_stored"],
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory
        }
