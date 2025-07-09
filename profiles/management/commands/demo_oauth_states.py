from django.core.management.base import BaseCommand
from django.conf import settings
import os
from utils.oauth_utils import get_google_oauth_status, is_google_oauth_enabled


class Command(BaseCommand):
    help = '演示 Google OAuth 在不同設定狀態下的系統行為'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-current',
            action='store_true',
            help='顯示當前 Google OAuth 設定狀態',
        )
        parser.add_argument(
            '--demo-modes',
            action='store_true',
            help='演示不同模式下的系統行為',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== Google OAuth 設定狀態演示 ===\n')
        )

        if options['show_current']:
            self.show_current_status()

        if options['demo_modes']:
            self.demo_different_modes()

        if not options['show_current'] and not options['demo_modes']:
            self.show_current_status()
            self.demo_different_modes()

    def show_current_status(self):
        """顯示當前設定狀態"""
        self.stdout.write(self.style.WARNING('📊 當前系統狀態：'))
        
        # 使用工具函數獲取狀態
        status = get_google_oauth_status()
        
        self.stdout.write(f'   • GOOGLE_OAUTH2_CLIENT_ID: {"✅ 已設定" if status["has_client_id"] else "❌ 未設定"}')
        self.stdout.write(f'   • GOOGLE_OAUTH2_CLIENT_SECRET: {"✅ 已設定" if status["has_client_secret"] else "❌ 未設定"}')
        self.stdout.write(f'   • GOOGLE_OAUTH_ENABLED: {"✅ True" if status["is_enabled"] else "❌ False"}')
        self.stdout.write(f'   • Google Provider 配置: {"✅ 已載入" if status["providers_configured"] else "❌ 未載入"}')
        
        self.stdout.write('')

    def demo_different_modes(self):
        """演示不同模式下的系統行為"""
        self.stdout.write(self.style.WARNING('🎭 系統行為演示：\n'))
        
        # 模式 1：已設定 Google OAuth
        self.stdout.write(self.style.SUCCESS('✅ 模式 1：已設定 Google OAuth'))
        self.stdout.write('   登入頁面：')
        self.stdout.write('   ┌─────────────────────────────────┐')
        self.stdout.write('   │ 使用者名稱: ________________   │')
        self.stdout.write('   │ 密碼: ____________________     │')
        self.stdout.write('   │ [登入]                         │')
        self.stdout.write('   │ ────────── 或 ──────────       │')
        self.stdout.write('   │ [🔵 使用 Google 登入]          │')
        self.stdout.write('   └─────────────────────────────────┘')
        self.stdout.write('')
        
        self.stdout.write('   個人資料頁面 → 第三方登入管理：')
        self.stdout.write('   ┌─────────────────────────────────┐')
        self.stdout.write('   │ Google                          │')
        self.stdout.write('   │ 已連結：user@gmail.com          │')
        self.stdout.write('   │ [取消連結] 或 [連結 Google]     │')
        self.stdout.write('   └─────────────────────────────────┘')
        self.stdout.write('')
        
        # 模式 2：未設定 Google OAuth
        self.stdout.write(self.style.ERROR('❌ 模式 2：未設定 Google OAuth'))
        self.stdout.write('   登入頁面：')
        self.stdout.write('   ┌─────────────────────────────────┐')
        self.stdout.write('   │ 使用者名稱: ________________   │')
        self.stdout.write('   │ 密碼: ____________________     │')
        self.stdout.write('   │ [登入]                         │')
        self.stdout.write('   │ ────────── 或 ──────────       │')
        self.stdout.write('   │ ⚠️ 第三方登入暫不可用           │')
        self.stdout.write('   │ 系統管理員尚未設定環境變數...   │')
        self.stdout.write('   └─────────────────────────────────┘')
        self.stdout.write('')
        
        self.stdout.write('   個人資料頁面 → 第三方登入管理：')
        self.stdout.write('   ┌─────────────────────────────────┐')
        self.stdout.write('   │ ⚠️ 第三方登入功能暫不可用        │')
        self.stdout.write('   │ 需要設定環境變數：              │')
        self.stdout.write('   │ • GOOGLE_OAUTH2_CLIENT_ID       │')
        self.stdout.write('   │ • GOOGLE_OAUTH2_CLIENT_SECRET   │')
        self.stdout.write('   │ [暫不可用]                     │')
        self.stdout.write('   └─────────────────────────────────┘')
        self.stdout.write('')
        
        # 關鍵特點
        self.stdout.write(self.style.SUCCESS('🔑 關鍵特點：'))
        self.stdout.write('   • 系統在兩種模式下都能正常運作')
        self.stdout.write('   • 沒有錯誤或崩潰')
        self.stdout.write('   • 友善的用戶提示訊息')
        self.stdout.write('   • 協作開發者可以直接使用超級使用者帳號')
        self.stdout.write('   • 動態檢測環境變數設定')
        self.stdout.write('')
        
        # 使用建議
        self.stdout.write(self.style.WARNING('💡 使用建議：'))
        self.stdout.write('')
        self.stdout.write('   👥 協作開發者（不需要 Google OAuth）：')
        self.stdout.write('      1. 直接 git clone 專案')
        self.stdout.write('      2. python manage.py createsuperuser')
        self.stdout.write('      3. python manage.py runserver')
        self.stdout.write('      4. 開始開發其他功能')
        self.stdout.write('')
        
        self.stdout.write('   🔧 需要 Google OAuth 功能的開發者：')
        self.stdout.write('      1. 按照 GOOGLE_OAUTH_SETUP.md 設定憑證')
        self.stdout.write('      2. 設定環境變數')
        self.stdout.write('      3. 重啟服務器')
        self.stdout.write('      4. 測試 Google 登入功能')
        self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('🎉 總結：此設計讓專案對協作者更友善！')) 