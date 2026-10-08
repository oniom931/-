# 입고일정 자동화

`3.발주현황`(일간 일정)을 읽어 `생산일정`의 `시트3` 달력에 모품목별 입고 일정을 적습니다.
규칙은 [CLAUDE.md](CLAUDE.md)에 정리돼 있습니다.

```
9/30 리파인-원료2종
입고완료 입고현황(2/4)
```

## 준비 (한 번만)
1. Google Cloud에서 서비스 계정을 만들고 **Google Sheets API**를 사용 설정한 뒤, JSON 키를 받습니다.
2. 서비스 계정 이메일을 시트에 공유합니다: `생산일정` → 편집자, `3.발주현황` → 뷰어.
3. 키를 환경 변수 `GOOGLE_SERVICE_ACCOUNT_JSON`으로 넣습니다 (한 줄 JSON 또는 base64).
   - Claude Code 클라우드: 환경 설정 → 환경 변수
   - GitHub Actions: 저장소 Settings → Secrets → `GOOGLE_SERVICE_ACCOUNT_JSON`
   - 키 파일은 저장소에 올리지 않습니다 (`.gitignore`에 등록됨).

## 사용
```bash
pip install -r requirements.txt
python -m receiving.cli show  --product 리프            # 정리 문구 출력
python -m receiving.cli apply --product 리프 --dry-run  # 바뀔 칸 미리보기
python -m receiving.cli apply --product 리프            # 시트3에 입력
python -m receiving.cli today                           # 오늘 입고 품목
```
GitHub Actions의 "시트3 입고일정 갱신" 워크플로를 수동 실행할 수도 있습니다 (매일 자동 실행은 워크플로 파일의 `schedule` 주석 해제).
