[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Restart-Prompt {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Yellow
    Write-Host "  词库已更新! 是否重启输入法使新词生效?" -ForegroundColor Yellow
    Write-Host "============================================" -ForegroundColor Yellow
    Write-Host ""
    $restart = Read-Host "重启输入法? (Y/N)"
    if ($restart.Trim().ToUpper() -eq "Y") {
        Write-Host "正在重启输入法..."
        & "$PSScriptRoot\restart_ime.bat"
    } else {
        Write-Host "跳过重启。可稍后双击 restart_ime.bat 手动重启。"
    }
    Read-Host "`n按回车继续"
}

function Show-Menu {
    Clear-Host
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "   AI IME - AI 扩词库工具 v1.2.0" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  [1] IT/计算机      [2] 财经/金融"
    Write-Host "  [3] 医学/医疗      [4] 成语"
    Write-Host "  [5] 地名/地理      [6] 诗词/古诗文"
    Write-Host "  [7] 历史名人/人名  [8] 饮食/美食"
    Write-Host "  [9] 法律           [0] 汽车"
    Write-Host "  [A] 动物           [B] 导入所有内置领域"
    Write-Host "  [C] 自定义领域(输入名称)"
    Write-Host "  [D] 查看可用领域列表"
    Write-Host "  [Q] 退出"
    Write-Host ""
}

$domainMap = @{
    "1" = "it"
    "2" = "财经"
    "3" = "医学"
    "4" = "成语"
    "5" = "地名"
    "6" = "诗词"
    "7" = "历史名人"
    "8" = "饮食"
    "9" = "法律"
    "0" = "汽车"
    "A" = "动物"
}

while ($true) {
    Show-Menu
    $choice = Read-Host "请选择"
    $choice = $choice.Trim().ToUpper()

    if ($choice -eq "Q") {
        break
    }

    if ($choice -eq "D") {
        python expand_lexicon.py --list
        Read-Host "`n按回车继续"
        continue
    }

    if ($choice -eq "B") {
        python expand_lexicon.py --all
        Restart-Prompt
        continue
    }

    if ($choice -eq "C") {
        $domain = Read-Host "请输入领域名称(如: 半导体, 线束制造, 航空航天)"
        if ($domain) {
            python expand_lexicon.py $domain
            Restart-Prompt
        }
        continue
    }

    if ($domainMap.ContainsKey($choice)) {
        python expand_lexicon.py $domainMap[$choice]
        Restart-Prompt
        continue
    }

    Write-Host "无效选择，按回车继续..." -ForegroundColor Red
    Read-Host
}
