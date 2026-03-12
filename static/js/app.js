$(function () {
    $(document).on("click", ".quiz-vote-btn", function () {
        const button = $(this);
        const quizId = button.data("quiz-id");
        const choice = button.data("choice");

        button.closest(".quiz-card").find(".quiz-vote-btn").prop("disabled", true);

        $.ajax({
            url: "/quiz/vote",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ quiz_id: quizId, choice: choice }),
        })
            .done(function (response) {
                const result = response.result;
                const container = $(`[data-quiz-result='${quizId}']`);
                container.html(`
                    <div class="quiz-result-labels">
                        <span>${result.left_label} ${result.left_rate}%</span>
                        <span>${result.right_label} ${result.right_rate}%</span>
                    </div>
                    <div class="progress rounded-pill" style="height: 12px;">
                        <div class="progress-bar bg-dark" role="progressbar" style="width: ${result.left_rate}%"></div>
                        <div class="progress-bar bg-warning" role="progressbar" style="width: ${result.right_rate}%"></div>
                    </div>
                    <p class="quiz-result-note mt-3 mb-1">${result.baseline_label} 기준 초기 비교 + 사용자 투표</p>
                    <p class="text-muted small mb-0">사용자 누적 투표 ${result.user_votes_total}건</p>
                `);
            })
            .fail(function () {
                alert("투표 처리 중 문제가 발생했습니다.");
            })
            .always(function () {
                button.closest(".quiz-card").find(".quiz-vote-btn").prop("disabled", false);
            });
    });

    $(document).on("click", ".content-feedback-btn", function () {
        const button = $(this);
        const contentId = button.data("content-id");
        const sentiment = button.data("sentiment");
        const group = $(`.content-feedback-btn[data-content-id='${contentId}']`);
        const message = $(`[data-feedback-message='${contentId}']`);

        group.prop("disabled", true);

        $.ajax({
            url: "/content/feedback",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ content_id: contentId, sentiment: sentiment }),
        })
            .done(function (response) {
                group.removeClass("active-feedback");
                $(`.content-feedback-btn[data-content-id='${contentId}'][data-sentiment='${sentiment}']`).addClass("active-feedback");
                message.text("학습 완료. 다음 추천부터 반영됩니다.");

                if (response.summary) {
                    $("[data-liked-count]").text(response.summary.liked_count);
                    $("[data-disliked-count]").text(response.summary.disliked_count);
                    $("[data-feedback-loop]").text("피드백 루프가 활성화되었습니다.");
                }
            })
            .fail(function (xhr) {
                const errorText = xhr.responseJSON?.message || "피드백 저장 중 문제가 발생했습니다.";
                message.text(errorText);
            })
            .always(function () {
                group.prop("disabled", false);
            });
    });
});
