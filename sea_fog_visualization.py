import json
import os
from datetime import datetime, timedelta
import numpy as np
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    import seaborn as sns
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib/seaborn not available. Chart generation will be limited.")

try:
    from sea_fog_prediction import SeaFogPredictionEngine
except ImportError:
    SeaFogPredictionEngine = None

class SeaFogVisualization:
    """海霧予測データの可視化システム"""
    
    def __init__(self):
        self.config_file = "sea_fog_viz_config.json"
        self.charts_dir = "charts"
        self.default_config = {
            "chart_settings": {
                "figure_size": [12, 8],
                "dpi": 100,
                "style": "seaborn-v0_8-whitegrid",
                "color_scheme": {
                    "low_risk": "#28a745",      # 緑色
                    "medium_risk": "#ffc107",   # 黄色
                    "high_risk": "#fd7e14",     # オレンジ色
                    "danger_risk": "#dc3545",   # 赤色
                    "background": "#f8f9fa",    # 薄い灰色
                    "grid": "#dee2e6"           # グリッド色
                }
            },
            "visualization_types": {
                "probability_timeline": True,
                "risk_heatmap": True,
                "condition_factors": True,
                "comparison_chart": True,
                "alert_distribution": True
            },
            "export_formats": ["png", "svg", "json"],
            "auto_refresh_interval": 300  # 5分間隔で自動更新
        }
        
        self.load_config()
        self.ensure_charts_directory()
        
        # 可視化用データの色分け設定
        self.risk_colors = {
            0: self.config["chart_settings"]["color_scheme"]["low_risk"],
            1: self.config["chart_settings"]["color_scheme"]["medium_risk"],
            2: self.config["chart_settings"]["color_scheme"]["high_risk"],
            3: self.config["chart_settings"]["color_scheme"]["danger_risk"]
        }
        
    def load_config(self):
        """設定ファイルの読み込み"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"Visualization config load error: {e}")
            self.config = self.default_config.copy()
    
    def save_config(self):
        """設定ファイルの保存"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Visualization config save error: {e}")
    
    def ensure_charts_directory(self):
        """チャート保存ディレクトリの作成"""
        try:
            os.makedirs(self.charts_dir, exist_ok=True)
        except Exception as e:
            print(f"Charts directory creation error: {e}")
    
    def generate_probability_timeline_chart(self, prediction_data, output_path=None):
        """海霧確率の時系列チャートを生成"""
        if not MATPLOTLIB_AVAILABLE:
            return {"error": "matplotlib not available"}
        
        try:
            hourly_predictions = prediction_data.get("hourly_predictions", [])
            if not hourly_predictions:
                return {"error": "予測データがありません"}
            
            # データの準備
            times = [datetime.fromisoformat(p["datetime"]) for p in hourly_predictions]
            probabilities = [p["fog_probability"] for p in hourly_predictions]
            alert_levels = [p["alert_level"]["level"] for p in hourly_predictions]
            
            # チャートの設定
            plt.style.use('default')
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=tuple(self.config["chart_settings"]["figure_size"]), 
                                         dpi=self.config["chart_settings"]["dpi"])
            
            # 上段：確率時系列
            ax1.plot(times, probabilities, linewidth=2, color='#007bff', marker='o', markersize=4)
            ax1.fill_between(times, probabilities, alpha=0.3, color='#007bff')
            
            # リスクレベル背景色
            for i, (time, level) in enumerate(zip(times, alert_levels)):
                if i < len(times) - 1:
                    next_time = times[i + 1]
                    color = self.risk_colors.get(level, '#28a745')
                    ax1.axvspan(time, next_time, alpha=0.2, color=color)
            
            ax1.set_title('海霧発生確率の時間推移', fontsize=14, fontweight='bold', pad=20)
            ax1.set_ylabel('発生確率', fontsize=12)
            ax1.set_ylim(0, 1)
            ax1.grid(True, alpha=0.3)
            
            # 作業時間帯のハイライト
            work_start = 4
            work_end = 16
            for time in times:
                if work_start <= time.hour <= work_end:
                    ax1.axvline(time, color='red', alpha=0.5, linestyle='--', linewidth=1)
            
            # 下段：アラートレベル
            colors = [self.risk_colors.get(level, '#28a745') for level in alert_levels]
            ax2.bar(times, alert_levels, color=colors, alpha=0.7, width=timedelta(hours=0.8))
            ax2.set_title('アラートレベル', fontsize=14, fontweight='bold', pad=20)
            ax2.set_ylabel('レベル', fontsize=12)
            ax2.set_ylim(-0.5, 3.5)
            ax2.set_yticks([0, 1, 2, 3])
            ax2.set_yticklabels(['正常', '注意', '警戒', '危険'])
            ax2.grid(True, alpha=0.3)
            
            # X軸の設定
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 保存
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(self.charts_dir, f"fog_timeline_{timestamp}.png")
            
            plt.savefig(output_path, bbox_inches='tight', facecolor='white')
            plt.close()
            
            return {
                "status": "success",
                "chart_path": output_path,
                "chart_type": "probability_timeline",
                "data_points": len(hourly_predictions)
            }
            
        except Exception as e:
            if 'fig' in locals():
                plt.close()
            return {"error": f"チャート生成エラー: {str(e)}"}
    
    def generate_risk_heatmap(self, spot_predictions, output_path=None):
        """複数地点の海霧リスクヒートマップを生成"""
        if not MATPLOTLIB_AVAILABLE:
            return {"error": "matplotlib not available"}
        
        try:
            if not spot_predictions:
                return {"error": "地点データがありません"}
            
            # データの準備
            spot_names = []
            max_probs = []
            avg_probs = []
            recommendations = []
            
            for spot in spot_predictions:
                spot_names.append(spot["spot_name"][:15])  # 名前を短縮
                max_probs.append(spot["fog_summary"]["overall_risk"]["maximum_probability"])
                avg_probs.append(spot["fog_summary"]["work_hours_risk"]["average_probability"])
                recommendations.append(spot["work_hours_recommendation"])
            
            # ヒートマップデータの作成
            data = np.array([max_probs, avg_probs]).T
            
            # チャートの設定
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(10, max(6, len(spot_names) * 0.4)))
            
            # ヒートマップの生成
            if 'sns' in globals():
                sns.heatmap(data, 
                           xticklabels=['最大確率', '作業時間平均'],
                           yticklabels=spot_names,
                           annot=True, 
                           fmt='.3f',
                           cmap='RdYlGn_r',
                           cbar_kws={'label': '海霧発生確率'},
                           ax=ax)
            else:
                # seabornが使えない場合はmatplotlibで代替
                im = ax.imshow(data, cmap='RdYlGn_r', aspect='auto')
                ax.set_xticks([0, 1])
                ax.set_xticklabels(['最大確率', '作業時間平均'])
                ax.set_yticks(range(len(spot_names)))
                ax.set_yticklabels(spot_names)
                
                # 数値をアノテーション
                for i in range(len(spot_names)):
                    for j in range(2):
                        text = ax.text(j, i, f'{data[i, j]:.3f}', 
                                     ha="center", va="center", color="black")
                
                plt.colorbar(im, ax=ax, label='海霧発生確率')
            
            ax.set_title('地点別海霧リスク分析', fontsize=14, fontweight='bold', pad=20)
            
            plt.tight_layout()
            
            # 保存
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(self.charts_dir, f"fog_heatmap_{timestamp}.png")
            
            plt.savefig(output_path, bbox_inches='tight', facecolor='white')
            plt.close()
            
            return {
                "status": "success",
                "chart_path": output_path,
                "chart_type": "risk_heatmap",
                "spots_analyzed": len(spot_names)
            }
            
        except Exception as e:
            if 'fig' in locals():
                plt.close()
            return {"error": f"ヒートマップ生成エラー: {str(e)}"}
    
    def generate_factors_chart(self, prediction_data, output_path=None):
        """海霧発生要因の分析チャートを生成"""
        if not MATPLOTLIB_AVAILABLE:
            return {"error": "matplotlib not available"}
        
        try:
            hourly_predictions = prediction_data.get("hourly_predictions", [])
            if not hourly_predictions:
                return {"error": "予測データがありません"}
            
            # 要因データの集計
            factor_names = []
            factor_values = []
            
            # 最初の予測から要因を取得
            sample_factors = hourly_predictions[0].get("factors", {})
            if sample_factors:
                factor_names = list(sample_factors.keys())
                factor_values = [[] for _ in factor_names]
                
                for prediction in hourly_predictions:
                    factors = prediction.get("factors", {})
                    for i, factor_name in enumerate(factor_names):
                        factor_values[i].append(factors.get(factor_name, 0))
            
            if not factor_names:
                return {"error": "要因データが見つかりません"}
            
            # チャートの設定
            plt.style.use('default')
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            axes = axes.flatten()
            
            times = [datetime.fromisoformat(p["datetime"]) for p in hourly_predictions]
            
            # 各要因の時系列プロット
            for i, (factor_name, values) in enumerate(zip(factor_names[:4], factor_values[:4])):
                if i < len(axes):
                    ax = axes[i]
                    ax.plot(times, values, linewidth=2, marker='o', markersize=3)
                    ax.fill_between(times, values, alpha=0.3)
                    ax.set_title(f'{factor_name}の影響度', fontsize=12)
                    ax.set_ylabel('影響度', fontsize=10)
                    ax.grid(True, alpha=0.3)
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            # 未使用のサブプロットを非表示
            for i in range(len(factor_names), len(axes)):
                axes[i].set_visible(False)
            
            plt.suptitle('海霧発生要因分析', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            # 保存
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(self.charts_dir, f"fog_factors_{timestamp}.png")
            
            plt.savefig(output_path, bbox_inches='tight', facecolor='white')
            plt.close()
            
            return {
                "status": "success",
                "chart_path": output_path,
                "chart_type": "factors_analysis",
                "factors_analyzed": len(factor_names)
            }
            
        except Exception as e:
            if 'fig' in locals():
                plt.close()
            return {"error": f"要因チャート生成エラー: {str(e)}"}
    
    def generate_comparison_chart(self, predictions_list, labels, output_path=None):
        """複数予測の比較チャートを生成"""
        if not MATPLOTLIB_AVAILABLE:
            return {"error": "matplotlib not available"}
        
        try:
            if len(predictions_list) != len(labels):
                return {"error": "予測データとラベルの数が一致しません"}
            
            # チャートの設定
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(12, 6))
            
            colors = ['#007bff', '#28a745', '#dc3545', '#ffc107']
            
            for i, (prediction_data, label) in enumerate(zip(predictions_list, labels)):
                hourly_predictions = prediction_data.get("hourly_predictions", [])
                if hourly_predictions:
                    times = [datetime.fromisoformat(p["datetime"]) for p in hourly_predictions]
                    probabilities = [p["fog_probability"] for p in hourly_predictions]
                    
                    color = colors[i % len(colors)]
                    ax.plot(times, probabilities, label=label, linewidth=2, 
                           color=color, marker='o', markersize=3)
            
            ax.set_title('地点別海霧確率比較', fontsize=14, fontweight='bold', pad=20)
            ax.set_ylabel('発生確率', fontsize=12)
            ax.set_ylim(0, 1)
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 保存
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(self.charts_dir, f"fog_comparison_{timestamp}.png")
            
            plt.savefig(output_path, bbox_inches='tight', facecolor='white')
            plt.close()
            
            return {
                "status": "success",
                "chart_path": output_path,
                "chart_type": "comparison",
                "predictions_compared": len(predictions_list)
            }
            
        except Exception as e:
            if 'fig' in locals():
                plt.close()
            return {"error": f"比較チャート生成エラー: {str(e)}"}
    
    def generate_web_dashboard_data(self, prediction_data):
        """Web表示用のダッシュボードデータを生成"""
        try:
            if not prediction_data or "hourly_predictions" not in prediction_data:
                return {"error": "予測データがありません"}
            
            hourly_predictions = prediction_data["hourly_predictions"]
            summary = prediction_data.get("summary", {})
            
            # 時系列データの準備
            timeline_data = []
            for prediction in hourly_predictions:
                timeline_data.append({
                    "time": prediction["datetime"],
                    "probability": prediction["fog_probability"],
                    "alert_level": prediction["alert_level"]["level"],
                    "alert_color": prediction["alert_level"]["color"],
                    "conditions": prediction.get("conditions", {})
                })
            
            # 作業時間帯のサマリー
            work_hours_data = []
            for prediction in hourly_predictions:
                hour = datetime.fromisoformat(prediction["datetime"]).hour
                if 4 <= hour <= 16:
                    work_hours_data.append({
                        "hour": hour,
                        "probability": prediction["fog_probability"],
                        "alert_level": prediction["alert_level"]["level"],
                        "recommendations": prediction.get("recommendations", [])
                    })
            
            # リスク分布
            risk_distribution = {"正常": 0, "注意": 0, "警戒": 0, "危険": 0}
            level_labels = ["正常", "注意", "警戒", "危険"]
            
            for prediction in hourly_predictions:
                level = prediction["alert_level"]["level"]
                if 0 <= level < len(level_labels):
                    risk_distribution[level_labels[level]] += 1
            
            # 最重要情報の抽出
            overall_risk = summary.get("overall_risk", {})
            work_risk = summary.get("work_hours_risk", {})
            
            dashboard_data = {
                "generated_at": datetime.now().isoformat(),
                "location": prediction_data.get("location", {}),
                "prediction_date": prediction_data.get("prediction_date"),
                "summary": {
                    "max_probability": overall_risk.get("maximum_probability", 0),
                    "peak_risk_time": overall_risk.get("peak_risk_time"),
                    "work_hours_average": work_risk.get("average_probability", 0),
                    "work_recommendation": work_risk.get("recommendation", "不明"),
                    "trend": summary.get("trend_analysis", "不明")
                },
                "timeline_data": timeline_data,
                "work_hours_data": work_hours_data,
                "risk_distribution": risk_distribution,
                "chart_config": {
                    "colors": self.risk_colors,
                    "risk_thresholds": [0.3, 0.6, 0.8]
                }
            }
            
            return dashboard_data
            
        except Exception as e:
            return {"error": f"ダッシュボードデータ生成エラー: {str(e)}"}
    
    def export_chart_data(self, chart_data, format_type="json", output_path=None):
        """チャートデータのエクスポート"""
        try:
            if format_type not in self.config["export_formats"]:
                return {"error": f"未対応の形式: {format_type}"}
            
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(self.charts_dir, f"fog_data_{timestamp}.{format_type}")
            
            if format_type == "json":
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(chart_data, f, ensure_ascii=False, indent=2)
                
                return {
                    "status": "success",
                    "export_path": output_path,
                    "format": format_type,
                    "size_bytes": os.path.getsize(output_path)
                }
            
            else:
                return {"error": f"形式 {format_type} の実装が必要です"}
                
        except Exception as e:
            return {"error": f"エクスポートエラー: {str(e)}"}
    
    def cleanup_old_charts(self, days_to_keep=7):
        """古いチャートファイルのクリーンアップ"""
        try:
            if not os.path.exists(self.charts_dir):
                return {"message": "チャートディレクトリが存在しません"}
            
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            removed_files = []
            
            for filename in os.listdir(self.charts_dir):
                file_path = os.path.join(self.charts_dir, filename)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < cutoff_time:
                        try:
                            os.remove(file_path)
                            removed_files.append(filename)
                        except Exception as e:
                            print(f"Failed to remove {filename}: {e}")
            
            return {
                "status": "success",
                "removed_files": removed_files,
                "removed_count": len(removed_files)
            }
            
        except Exception as e:
            return {"error": f"クリーンアップエラー: {str(e)}"}

if __name__ == "__main__":
    # テスト実行
    print("=== Sea Fog Visualization Test ===")
    
    viz = SeaFogVisualization()
    
    # サンプルデータでテスト
    sample_prediction = {
        "hourly_predictions": [
            {
                "datetime": datetime.now().isoformat(),
                "fog_probability": 0.3,
                "alert_level": {"level": 1, "color": "yellow"},
                "factors": {"temperature": 0.2, "humidity": 0.3, "wind": 0.1},
                "conditions": {"temperature": 12, "humidity": 85},
                "recommendations": ["注意が必要"]
            }
        ],
        "summary": {
            "overall_risk": {"maximum_probability": 0.3, "peak_risk_time": datetime.now().isoformat()},
            "work_hours_risk": {"average_probability": 0.25, "recommendation": "要注意"},
            "trend_analysis": "安定"
        }
    }
    
    # Web用データ生成テスト
    dashboard_data = viz.generate_web_dashboard_data(sample_prediction)
    if "error" not in dashboard_data:
        print("OK Dashboard data generated")
        print(f"  Timeline points: {len(dashboard_data['timeline_data'])}")
        print(f"  Work hours points: {len(dashboard_data['work_hours_data'])}")
    else:
        print(f"Dashboard generation failed: {dashboard_data['error']}")
    
    # エクスポートテスト
    export_result = viz.export_chart_data(dashboard_data, "json")
    if export_result.get("status") == "success":
        print(f"OK Data exported to {export_result['export_path']}")
    else:
        print(f"Export failed: {export_result.get('error')}")
    
    print("\\n=== Test Completed ===")