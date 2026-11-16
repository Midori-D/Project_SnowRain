import Foundation

struct StoryProgram: Decodable {
    struct Layer: Decodable {
        let image: String
        let x: Double?
        let y: Double?
        let width: Double?
        let height: Double?
        let opacity: Double?
        let mirrored: Bool?
        let sourceX: Double?
        let sourceY: Double?
        let sourceWidth: Double?
        let sourceHeight: Double?
    }

    struct Choice: Decodable, Identifiable {
        let text: String
        let target: String
        var id: String { text }
    }

    struct Beat: Decodable {
        let text: String?
        let speaker: String?
        let background: String?
        let layers: [Layer]?
        let music: String?
        let effect: String?
        let date: String?
        let growthStat: Int?
        let delay: Double?
        let sceneHeight: Double?
        let next: String?
        let choices: [Choice]?
        let end: String?
    }

    let version: Int
    let start: String
    let title: String?
    let titleMusic: String?
    let firstActivity: String?
    let canvasWidth: Double?
    let canvasHeight: Double?
    let beats: [String: Beat]

    func validate(hasFile: (String) -> Bool) throws {
        guard version == 1, beats[start] != nil, !beats.isEmpty,
              firstActivity.map({ beats[$0] != nil }) ?? true,
              (canvasWidth ?? 360).isFinite, (canvasHeight ?? 530).isFinite,
              (1...2048).contains(canvasWidth ?? 360),
              (1...2048).contains(canvasHeight ?? 530) else {
            throw StoryError.invalidProgram
        }
        for asset in [title, titleMusic].compactMap({ $0 }) where !hasFile(asset) {
            throw StoryError.missingAsset(asset)
        }
        for (id, beat) in beats {
            let choices = beat.choices ?? []
            let exitCount = (beat.next == nil ? 0 : 1) + (choices.isEmpty ? 0 : 1) + (beat.end == nil ? 0 : 1)
            let targets = choices.map(\.target) + [beat.next].compactMap { $0 }
            guard exitCount == 1, Set(choices.map(\.text)).count == choices.count,
                  targets.allSatisfy({ beats[$0] != nil }),
                  beat.growthStat.map({ (0..<4).contains($0) }) ?? true,
                  (0...60).contains(beat.delay ?? 0),
                  (1...2048).contains(beat.sceneHeight ?? 530) else {
                throw StoryError.invalidBeat(id)
            }
            let assets = [beat.background, beat.music, beat.effect].compactMap { $0 } + (beat.layers ?? []).map(\.image)
            for asset in assets where !hasFile(asset) {
                throw StoryError.missingAsset(asset)
            }
        }
    }
}

struct StorySave: Codable {
    let programID: String
    let beatID: String
    var growth: GrowthStats? = nil
}

struct GrowthStats: Codable, Equatable {
    static let names = ["학습", "운동", "매력", "감성"]
    private(set) var values = [50, 50, 50, 50]

    mutating func perform(activity: Int, roll: Int) {
        // Original ARMv7 _vProcessGrowAniMation and _upstate.
        let changes = roll < 200 ? [2, 0, -1, -2] : roll < 700 ? [4, 1, 0, 0] : [6, 2, 1, 0]
        let order = [[0, 2, 3, 1], [2, 0, 1, 3], [3, 1, 0, 2], [1, 3, 2, 0]]
        values = zip(values, order[activity]).map { min(300, $0 + changes[$1]) }
    }

    init() {}

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let decoded = try container.decode([Int].self)
        guard decoded.count == 4, decoded.allSatisfy({ (-32_768...300).contains($0) }) else {
            throw StoryError.invalidProgram
        }
        values = decoded
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(values)
    }
}

enum StoryError: LocalizedError {
    case invalidArchive
    case missingProgram
    case invalidProgram
    case invalidBeat(String)
    case missingAsset(String)

    var errorDescription: String? {
        switch self {
        case .invalidArchive: return "데이터 ZIP의 형식 또는 무결성을 확인할 수 없습니다."
        case .missingProgram: return "이 데이터 묶음에 재생할 스노우레인 시나리오가 없습니다."
        case .invalidProgram: return "이 버전에서는 이 시나리오를 열 수 없습니다."
        case .invalidBeat(let id): return "시나리오 연결이 잘못되었습니다. 장면 \(id)"
        case .missingAsset(let name): return "데이터 묶음에 필요한 파일이 없습니다. \(name)"
        }
    }
}
