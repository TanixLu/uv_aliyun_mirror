use axum::{
    extract::Path,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::get,
    Router,
};
use std::path::Path as FsPath;
use tokio::net::TcpListener;

async fn handle_get(Path(req_path): Path<String>) -> Response {
    let full_path = FsPath::new("/mnt/oss").join(&req_path);

    if full_path.exists() && full_path.is_file() {
        match tokio::fs::read(&full_path).await {
            Ok(file_content) => {
                Response::builder()
                    .status(StatusCode::OK)
                    .body(axum::body::Body::from(file_content))
                    .unwrap()
            }
            Err(_) => not_found(),
        }
    } else {
        not_found()
    }
}

fn not_found() -> Response {
    (StatusCode::NOT_FOUND, "404 Not Found").into_response()
}

#[tokio::main]
async fn main() {
    let app = Router::new().route("/{*req_path}", get(handle_get));

    let listener = TcpListener::bind( "0.0.0.0:9000").await.unwrap();
    axum::serve(listener, app.into_make_service())
        .await
        .unwrap();
}
