from pathlib import Path

from flask import Flask

from app.document_parser import DocumentParser
from app.routes import main_bp
from app.services import DocumentProcessingService
from config import Config
from db.mongo import MongoRepository
from ocr.extractor import OCRService
from rules.engine import RuleEngine


def create_app():
    app = Flask(
        __name__,
        template_folder=str(Config.BASE_DIR / "templates"),
        static_folder=str(Config.BASE_DIR / "static"),
    )
    app.config.from_object(Config)

    upload_dir = Path(app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    repository = MongoRepository(
        mongo_uri=app.config["MONGO_URI"],
        db_name=app.config["MONGO_DB_NAME"],
    )
    ocr_service = OCRService(
        language=app.config["OCR_LANGUAGE"],
        max_pages=app.config["OCR_MAX_PAGES"],
    )
    parser = DocumentParser(
        api_key=app.config["OPENAI_API_KEY"],
        model=app.config["OPENAI_MODEL"],
        api_url=app.config["OPENAI_API_URL"],
    )
    rule_engine = RuleEngine(app.config["RULES_FILE"])
    document_service = DocumentProcessingService(
        repository=repository,
        ocr_service=ocr_service,
        parser=parser,
        rule_engine=rule_engine,
        upload_folder=upload_dir,
        allowed_extensions=app.config["ALLOWED_EXTENSIONS"],
        auto_delete_original=app.config["AUTO_DELETE_ORIGINAL"],
    )

    app.extensions["repository"] = repository
    app.extensions["ocr_service"] = ocr_service
    app.extensions["parser"] = parser
    app.extensions["rule_engine"] = rule_engine
    app.extensions["document_service"] = document_service

    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_template_helpers():
        document_type_labels = {
            "medical_certificate": "진단서 / 진료확인서",
            "medical_receipt": "의료 영수증 / 결제내역서",
            "funeral_certificate": "장례 관련 증빙",
            "competition_participation": "대회 참가 확인서",
            "counseling_confirmation": "상담 확인서",
            "unknown": "미분류",
        }
        return {"document_type_labels": document_type_labels}

    return app
