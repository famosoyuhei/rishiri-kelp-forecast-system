import os
import json
from datetime import datetime
from typing import List, Dict, Optional

class FavoritesManager:
    """利尻島昆布干場 お気に入り管理システム"""
    
    def __init__(self):
        self.favorites_file = "user_favorites.json"
        self.settings_file = "favorites_settings.json"
        
        self.default_settings = {
            "max_favorites": 20,           # 最大お気に入り数
            "quick_access_count": 5,       # クイックアクセス表示数
            "auto_sort": True,             # 自動ソート（使用頻度順）
            "show_weather_preview": True,  # 天気プレビュー表示
            "show_last_record": True,      # 最終記録表示
            "notification_for_favorites": True,  # お気に入り専用通知
            "export_enabled": True,        # エクスポート機能
            "sync_across_devices": False   # デバイス間同期（将来機能）
        }
        
        self.load_settings()
        self.load_favorites()
    
    def load_settings(self):
        """設定ファイルの読み込み"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                self.settings = self.default_settings.copy()
                self.settings.update(loaded_settings)
            else:
                self.settings = self.default_settings.copy()
                self.save_settings()
        except Exception as e:
            print(f"Favorites settings load error: {e}")
            self.settings = self.default_settings.copy()
    
    def save_settings(self):
        """設定ファイルの保存"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Favorites settings save error: {e}")
            return False
    
    def load_favorites(self):
        """お気に入りファイルの読み込み"""
        try:
            if os.path.exists(self.favorites_file):
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
            else:
                self.favorites = []
                self.save_favorites()
        except Exception as e:
            print(f"Favorites load error: {e}")
            self.favorites = []
    
    def save_favorites(self):
        """お気に入りファイルの保存"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Favorites save error: {e}")
            return False
    
    def add_favorite(self, spot_name: str, spot_data: Dict) -> Dict:
        """お気に入りに追加"""
        try:
            # 既に登録済みかチェック
            if self.is_favorite(spot_name):
                return {
                    "status": "error",
                    "message": "既にお気に入りに登録されています"
                }
            
            # 最大数チェック
            if len(self.favorites) >= self.settings["max_favorites"]:
                return {
                    "status": "error", 
                    "message": f"お気に入りの最大数（{self.settings['max_favorites']}個）に達しています"
                }
            
            # お気に入り項目の作成
            favorite_item = {
                "id": len(self.favorites) + 1,
                "name": spot_name,
                "lat": spot_data.get("lat"),
                "lon": spot_data.get("lon"),
                "added_at": datetime.now().isoformat(),
                "access_count": 0,
                "last_accessed": None,
                "last_forecast_result": None,
                "last_record": None,
                "custom_note": "",
                "color_tag": "default",  # お気に入りの色分け
                "quick_access": len(self.favorites) < self.settings["quick_access_count"],
                "notification_enabled": self.settings["notification_for_favorites"]
            }
            
            self.favorites.append(favorite_item)
            self.save_favorites()
            
            return {
                "status": "success",
                "message": "お気に入りに追加しました",
                "favorite_id": favorite_item["id"]
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"お気に入り追加エラー: {str(e)}"
            }
    
    def remove_favorite(self, spot_name: str) -> Dict:
        """お気に入りから削除"""
        try:
            original_count = len(self.favorites)
            self.favorites = [f for f in self.favorites if f["name"] != spot_name]
            
            if len(self.favorites) < original_count:
                self.save_favorites()
                return {
                    "status": "success",
                    "message": "お気に入りから削除しました"
                }
            else:
                return {
                    "status": "error",
                    "message": "お気に入りに登録されていません"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"お気に入り削除エラー: {str(e)}"
            }
    
    def is_favorite(self, spot_name: str) -> bool:
        """お気に入りに登録されているかチェック"""
        return any(f["name"] == spot_name for f in self.favorites)
    
    def get_favorite(self, spot_name: str) -> Optional[Dict]:
        """特定のお気に入り項目を取得"""
        for favorite in self.favorites:
            if favorite["name"] == spot_name:
                return favorite
        return None
    
    def update_access(self, spot_name: str) -> bool:
        """アクセス情報を更新"""
        try:
            for favorite in self.favorites:
                if favorite["name"] == spot_name:
                    favorite["access_count"] += 1
                    favorite["last_accessed"] = datetime.now().isoformat()
                    
                    # 自動ソートが有効な場合、使用頻度順に並び替え
                    if self.settings["auto_sort"]:
                        self.favorites.sort(key=lambda x: x["access_count"], reverse=True)
                    
                    self.save_favorites()
                    return True
            return False
        except Exception as e:
            print(f"Access update error: {e}")
            return False
    
    def update_forecast_result(self, spot_name: str, forecast_result: str) -> bool:
        """予報結果を更新"""
        try:
            for favorite in self.favorites:
                if favorite["name"] == spot_name:
                    favorite["last_forecast_result"] = {
                        "result": forecast_result,
                        "updated_at": datetime.now().isoformat()
                    }
                    self.save_favorites()
                    return True
            return False
        except Exception as e:
            print(f"Forecast result update error: {e}")
            return False
    
    def update_record(self, spot_name: str, record_result: str) -> bool:
        """記録を更新"""
        try:
            for favorite in self.favorites:
                if favorite["name"] == spot_name:
                    favorite["last_record"] = {
                        "result": record_result,
                        "updated_at": datetime.now().isoformat()
                    }
                    self.save_favorites()
                    return True
            return False
        except Exception as e:
            print(f"Record update error: {e}")
            return False
    
    def update_custom_note(self, spot_name: str, note: str) -> bool:
        """カスタムメモを更新"""
        try:
            for favorite in self.favorites:
                if favorite["name"] == spot_name:
                    favorite["custom_note"] = note
                    favorite["updated_at"] = datetime.now().isoformat()
                    self.save_favorites()
                    return True
            return False
        except Exception as e:
            print(f"Custom note update error: {e}")
            return False
    
    def set_color_tag(self, spot_name: str, color_tag: str) -> bool:
        """色タグを設定"""
        valid_colors = ["default", "red", "blue", "green", "yellow", "purple", "orange"]
        
        if color_tag not in valid_colors:
            return False
        
        try:
            for favorite in self.favorites:
                if favorite["name"] == spot_name:
                    favorite["color_tag"] = color_tag
                    self.save_favorites()
                    return True
            return False
        except Exception as e:
            print(f"Color tag update error: {e}")
            return False
    
    def toggle_quick_access(self, spot_name: str) -> Dict:
        """クイックアクセスの切り替え"""
        try:
            favorite = self.get_favorite(spot_name)
            if not favorite:
                return {"status": "error", "message": "お気に入りに登録されていません"}
            
            # クイックアクセス数の制限チェック
            if not favorite["quick_access"]:
                quick_access_count = sum(1 for f in self.favorites if f["quick_access"])
                if quick_access_count >= self.settings["quick_access_count"]:
                    return {
                        "status": "error", 
                        "message": f"クイックアクセスの最大数（{self.settings['quick_access_count']}個）に達しています"
                    }
            
            # 切り替え
            for favorite in self.favorites:
                if favorite["name"] == spot_name:
                    favorite["quick_access"] = not favorite["quick_access"]
                    self.save_favorites()
                    
                    status_text = "有効" if favorite["quick_access"] else "無効"
                    return {
                        "status": "success",
                        "message": f"クイックアクセスを{status_text}にしました",
                        "quick_access": favorite["quick_access"]
                    }
            
            return {"status": "error", "message": "更新に失敗しました"}
            
        except Exception as e:
            return {"status": "error", "message": f"エラー: {str(e)}"}
    
    def get_all_favorites(self, sort_by: str = "auto") -> List[Dict]:
        """すべてのお気に入りを取得"""
        try:
            favorites_copy = self.favorites.copy()
            
            if sort_by == "name":
                favorites_copy.sort(key=lambda x: x["name"])
            elif sort_by == "added_date":
                favorites_copy.sort(key=lambda x: x["added_at"], reverse=True)
            elif sort_by == "access_count":
                favorites_copy.sort(key=lambda x: x["access_count"], reverse=True)
            elif sort_by == "last_accessed":
                favorites_copy.sort(key=lambda x: x["last_accessed"] or "0", reverse=True)
            # "auto"の場合は現在の順序を維持
            
            return favorites_copy
        except Exception as e:
            print(f"Get favorites error: {e}")
            return []
    
    def get_quick_access_favorites(self) -> List[Dict]:
        """クイックアクセス用お気に入りを取得"""
        try:
            quick_favorites = [f for f in self.favorites if f["quick_access"]]
            
            # 使用頻度順にソート
            quick_favorites.sort(key=lambda x: x["access_count"], reverse=True)
            
            return quick_favorites
        except Exception as e:
            print(f"Get quick access error: {e}")
            return []
    
    def search_favorites(self, query: str) -> List[Dict]:
        """お気に入りを検索"""
        try:
            query_lower = query.lower()
            results = []
            
            for favorite in self.favorites:
                # 名前、メモで検索
                if (query_lower in favorite["name"].lower() or 
                    query_lower in favorite.get("custom_note", "").lower()):
                    results.append(favorite)
            
            return results
        except Exception as e:
            print(f"Search favorites error: {e}")
            return []
    
    def get_favorites_summary(self) -> Dict:
        """お気に入りサマリーを取得"""
        try:
            total_count = len(self.favorites)
            quick_access_count = sum(1 for f in self.favorites if f["quick_access"])
            
            # 色タグ別集計
            color_stats = {}
            for favorite in self.favorites:
                color = favorite.get("color_tag", "default")
                color_stats[color] = color_stats.get(color, 0) + 1
            
            # 最近アクセスした項目
            recent_favorites = [f for f in self.favorites if f["last_accessed"]]
            recent_favorites.sort(key=lambda x: x["last_accessed"], reverse=True)
            recent_favorites = recent_favorites[:3]  # 最新3件
            
            # 統計情報
            total_access = sum(f["access_count"] for f in self.favorites)
            avg_access = total_access / total_count if total_count > 0 else 0
            
            return {
                "total_count": total_count,
                "quick_access_count": quick_access_count,
                "max_favorites": self.settings["max_favorites"],
                "max_quick_access": self.settings["quick_access_count"],
                "color_stats": color_stats,
                "recent_favorites": recent_favorites,
                "total_access_count": total_access,
                "average_access_count": round(avg_access, 1),
                "settings": self.settings
            }
            
        except Exception as e:
            print(f"Get summary error: {e}")
            return {
                "total_count": 0,
                "quick_access_count": 0,
                "error": str(e)
            }
    
    def export_favorites(self) -> Dict:
        """お気に入りをエクスポート"""
        try:
            if not self.settings["export_enabled"]:
                return {"status": "error", "message": "エクスポート機能が無効です"}
            
            export_data = {
                "export_date": datetime.now().isoformat(),
                "version": "1.0",
                "favorites": self.favorites,
                "settings": self.settings
            }
            
            export_filename = f"konbu_favorites_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(export_filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return {
                "status": "success",
                "message": "お気に入りをエクスポートしました",
                "filename": export_filename,
                "count": len(self.favorites)
            }
            
        except Exception as e:
            return {"status": "error", "message": f"エクスポートエラー: {str(e)}"}
    
    def import_favorites(self, import_file: str, merge_mode: bool = True) -> Dict:
        """お気に入りをインポート"""
        try:
            if not os.path.exists(import_file):
                return {"status": "error", "message": "インポートファイルが見つかりません"}
            
            with open(import_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            if "favorites" not in import_data:
                return {"status": "error", "message": "無効なインポートファイル形式です"}
            
            imported_favorites = import_data["favorites"]
            
            if merge_mode:
                # マージモード：既存と重複しないもののみ追加
                existing_names = {f["name"] for f in self.favorites}
                new_favorites = [f for f in imported_favorites if f["name"] not in existing_names]
                
                # 最大数チェック
                if len(self.favorites) + len(new_favorites) > self.settings["max_favorites"]:
                    max_new = self.settings["max_favorites"] - len(self.favorites)
                    new_favorites = new_favorites[:max_new]
                
                self.favorites.extend(new_favorites)
                action = f"{len(new_favorites)}個の新しいお気に入りを追加"
            else:
                # 置換モード：すべて置き換え
                self.favorites = imported_favorites[:self.settings["max_favorites"]]
                action = f"{len(self.favorites)}個のお気に入りで置き換え"
            
            self.save_favorites()
            
            return {
                "status": "success",
                "message": f"インポート完了: {action}",
                "imported_count": len(imported_favorites),
                "current_count": len(self.favorites)
            }
            
        except Exception as e:
            return {"status": "error", "message": f"インポートエラー: {str(e)}"}
    
    def cleanup_favorites(self) -> Dict:
        """お気に入りのクリーンアップ"""
        try:
            original_count = len(self.favorites)
            
            # 無効なデータの削除
            valid_favorites = []
            for favorite in self.favorites:
                if (favorite.get("name") and 
                    favorite.get("lat") is not None and 
                    favorite.get("lon") is not None):
                    valid_favorites.append(favorite)
            
            # IDの振り直し
            for i, favorite in enumerate(valid_favorites):
                favorite["id"] = i + 1
            
            self.favorites = valid_favorites
            self.save_favorites()
            
            cleaned_count = original_count - len(self.favorites)
            
            return {
                "status": "success",
                "message": f"クリーンアップ完了: {cleaned_count}個の無効な項目を削除",
                "cleaned_count": cleaned_count,
                "current_count": len(self.favorites)
            }
            
        except Exception as e:
            return {"status": "error", "message": f"クリーンアップエラー: {str(e)}"}

if __name__ == "__main__":
    # テスト実行
    print("=== Favorites Manager テスト ===")
    
    favorites = FavoritesManager()
    
    # テスト用干場データ
    test_spots = [
        {"name": "沓形港前", "lat": 45.210, "lon": 141.200},
        {"name": "仙法志港", "lat": 45.136, "lon": 141.211},
        {"name": "鴛泊港", "lat": 45.242, "lon": 141.231}
    ]
    
    # お気に入り追加テスト
    print("\nお気に入り追加テスト:")
    for spot in test_spots:
        result = favorites.add_favorite(spot["name"], spot)
        print(f"  {spot['name']}: {result['status']}")
    
    # お気に入り一覧
    print("\nお気に入り一覧:")
    all_favorites = favorites.get_all_favorites()
    for fav in all_favorites:
        print(f"  - {fav['name']} (アクセス数: {fav['access_count']})")
    
    # アクセス更新テスト
    print("\nアクセス更新テスト:")
    favorites.update_access("沓形港前")
    favorites.update_access("沓形港前")
    
    # サマリー表示
    summary = favorites.get_favorites_summary()
    print(f"\nサマリー:")
    print(f"  総数: {summary['total_count']}")
    print(f"  クイックアクセス: {summary['quick_access_count']}")
    print(f"  総アクセス数: {summary['total_access_count']}")
    
    print("\n=== テスト完了 ===")