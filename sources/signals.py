"""
Sources 應用的信號處理器
"""

import os
from django.db.models.signals import pre_delete
from django.dispatch import receiver


@receiver(pre_delete, sender='sources.SourceFile')
def delete_source_file_physical_file(sender, instance, **kwargs):
    """
    當 SourceFile 被刪除時（包括 CASCADE 刪除），自動刪除實體檔案
    
    這個信號處理器確保無論是直接刪除還是透過 CASCADE 刪除，
    都會正確清理實體檔案，避免檔案系統中的孤兒檔案。
    
    Args:
        sender: 發送信號的模型類別
        instance: 被刪除的 SourceFile 實例
        **kwargs: 其他信號參數
    """
    if instance.path and os.path.exists(instance.path):
        try:
            # 刪除實體檔案
            os.remove(instance.path)
            print(f"✅ 已刪除實體檔案：{instance.path}")
            
            # 檢查並刪除空的父目錄
            parent_dir = os.path.dirname(instance.path)
            try:
                # 只有當目錄為空時才刪除
                if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
                    print(f"✅ 已刪除空目錄：{parent_dir}")
                    
                    # 繼續檢查上一層目錄
                    grandparent_dir = os.path.dirname(parent_dir)
                    if os.path.exists(grandparent_dir) and not os.listdir(grandparent_dir):
                        os.rmdir(grandparent_dir)
                        print(f"✅ 已刪除空目錄：{grandparent_dir}")
            except OSError as e:
                # 如果無法刪除目錄（可能不為空或權限問題），忽略錯誤
                print(f"⚠️  無法刪除目錄 {parent_dir}：{e}")
                pass
        except OSError as e:
            # 如果無法刪除檔案，記錄錯誤但不中斷流程
            print(f"⚠️  無法刪除檔案 {instance.path}：{e}")
            pass
    else:
        if instance.path:
            print(f"⚠️  檔案不存在，跳過刪除：{instance.path}")
        else:
            print("⚠️  檔案路徑為空，跳過刪除") 