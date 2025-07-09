from django.core.management.base import BaseCommand
from utils.oauth_utils import check_google_oauth_redirect, get_google_oauth_status


class Command(BaseCommand):
    help = '檢查 Google OAuth 重新導向 URL 設定'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== Google OAuth 重新導向檢查 ===\n')
        )

        # 首先檢查基本 OAuth 狀態
        self.stdout.write(self.style.WARNING('📊 基本 OAuth 狀態：'))
        status = get_google_oauth_status()
        
        self.stdout.write(f'   • Google OAuth 是否啟用: {"✅" if status["is_enabled"] else "❌"} {status["is_enabled"]}')
        self.stdout.write(f'   • Client ID 是否設定: {"✅" if status["has_client_id"] else "❌"} {status["has_client_id"]}')
        self.stdout.write(f'   • Client Secret 是否設定: {"✅" if status["has_client_secret"] else "❌"} {status["has_client_secret"]}')
        self.stdout.write('')

        # 檢查重新導向 URL
        self.stdout.write(self.style.WARNING('🔄 重新導向 URL 檢查：'))
        
        redirect_result = check_google_oauth_redirect()
        
        if redirect_result['status'] == 'success':
            self.stdout.write(
                self.style.SUCCESS(
                    f'   • Adapter callback_url: {redirect_result["adapter_callback_url"]}'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'   • Settings REDIRECT_URI: {redirect_result["settings_redirect_uri"]}'
                )
            )
            
            # 提供建議
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('💡 設定建議：'))
            
            if redirect_result["adapter_callback_url"]:
                self.stdout.write(f'   請確保在 Google Cloud Console 中設定以下重新導向 URI：')
                self.stdout.write(f'   {redirect_result["adapter_callback_url"]}')
            
            if redirect_result["settings_redirect_uri"]:
                self.stdout.write(f'   您在 settings.py 中自定義的重新導向 URI：')
                self.stdout.write(f'   {redirect_result["settings_redirect_uri"]}')
            else:
                self.stdout.write('   您沒有在 settings.py 中設定自定義的 REDIRECT_URI')
                self.stdout.write('   系統將使用預設的重新導向 URL')
                
        else:
            self.stdout.write(
                self.style.ERROR(f'   ❌ 檢查失敗: {redirect_result["error"]}')
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('檢查完成！')) 