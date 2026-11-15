import SwiftUI

@main
struct SnowRainApp: App {
    var body: some Scene {
        WindowGroup {
            OpeningView()
        }
    }
}

struct OpeningView: View {
    @AppStorage("openingParagraph") private var savedParagraph = 0
    @State private var paragraphs: [String] = []
    @State private var loadError: String?

    private var currentParagraph: Int {
        min(max(savedParagraph, 0), max(paragraphs.count - 1, 0))
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Text("오프닝 대사 확인용 개발판")
                    .font(.headline)
                Text("선택지, 호감도, 배경 연출은 구현 중입니다.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                if let loadError {
                    Text(loadError)
                        .foregroundStyle(.red)
                } else if !paragraphs.isEmpty {
                    ScrollView {
                        Text(paragraphs[currentParagraph])
                            .font(.title3)
                            .lineSpacing(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                    }
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
                    Text("\(currentParagraph + 1) / \(paragraphs.count)")
                        .font(.caption.monospacedDigit())
                    HStack {
                        Button("이전") { savedParagraph = currentParagraph - 1 }
                            .disabled(currentParagraph == 0)
                        Spacer()
                        Button("다음") { savedParagraph = currentParagraph + 1 }
                            .disabled(currentParagraph + 1 >= paragraphs.count)
                    }
                    .buttonStyle(.borderedProminent)
                    Button("처음부터") { savedParagraph = 0 }
                    Text("읽던 위치는 자동으로 저장됩니다.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }
            .padding()
            .navigationTitle("SnowRain")
            .task { loadOpening() }
        }
    }

    private func loadOpening() {
        do {
            guard let url = Bundle.main.url(forResource: "opening", withExtension: "json") else {
                loadError = "오프닝 데이터가 빌드에 포함되지 않았습니다."
                return
            }
            paragraphs = try JSONDecoder().decode([String].self, from: Data(contentsOf: url))
            if paragraphs.isEmpty {
                loadError = "오프닝 대사가 비어 있습니다."
            }
        } catch {
            loadError = "오프닝 데이터를 읽을 수 없습니다. \(error.localizedDescription)"
        }
    }
}
