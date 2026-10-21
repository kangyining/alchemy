"""Report history and download routes, with storage supplied by the application."""
from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response


def install_report_routes(app, list_runs, get_bucket):
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/reports/{user_id}")
    async def list_reports(user_id: str):
        return JSONResponse(content=list_runs(user_id))

    @app.get("/reports/{user_id}/{filename}")
    async def download_report(user_id: str, filename: str):
        if not filename.endswith((".pdf", ".pptx")):
            raise HTTPException(status_code=404, detail="Report not found")
        blob = get_bucket().blob(f"{user_id}/{filename}")
        if not blob.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        media_type = "application/pdf" if filename.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return Response(content=blob.download_as_bytes(), media_type=media_type,
                        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})
