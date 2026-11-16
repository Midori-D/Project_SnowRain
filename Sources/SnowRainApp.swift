import AVFoundation
import SwiftUI
import UniformTypeIdentifiers

@main
struct SnowRainApp: App {
    var body: some Scene {
        WindowGroup { GameView() }
    }
}

private struct GameView: View {
    @AppStorage("storySaveV1") private var saved = Data()
    @AppStorage("storyMuted") private var muted = false
    @State private var library: GameLibrary?
    @State private var beatID: String?
    @State private var growth = GrowthStats()
    @State private var pickingArchive = false
    @State private var importing = false
    @State private var confirmingActivityJump = false
    @State private var problem: String?
    @StateObject private var audio = SceneAudio()

    private var beat: StoryProgram.Beat? {
        guard let beatID else { return nil }
        return library?.package.program.beats[beatID]
    }

    private var resumeSave: StorySave? {
        guard let library, let save = try? JSONDecoder().decode(StorySave.self, from: saved),
              save.programID == library.package.id, library.package.program.beats[save.beatID] != nil else { return nil }
        return save
    }

    var body: some View {
        GeometryReader { space in
            if let library, let beat {
                playView(library: library, beat: beat, size: space.size)
            } else {
                titleView
            }
        }
        .foregroundStyle(.white)
        .background(Color(red: 0.05, green: 0.09, blue: 0.15).ignoresSafeArea())
        .preferredColorScheme(.dark)
        .fileImporter(isPresented: $pickingArchive, allowedContentTypes: [.zip]) { result in
            switch result {
            case .success(let url): importArchive(url)
            case .failure(let error): problem = error.localizedDescription
            }
        }
        .alert("스노우레인", isPresented: Binding(
            get: { problem != nil },
            set: { if !$0 { problem = nil } }
        )) {
            Button("확인", role: .cancel) { problem = nil }
        } message: {
            Text(problem ?? "")
        }
        .confirmationDialog("첫 평일 메뉴로 이동할까요?", isPresented: $confirmingActivityJump, titleVisibility: .visible) {
            Button("첫 평일 메뉴로 이동") {
                if let id = library?.package.program.firstActivity { start(at: id) }
            }
        } message: {
            Text("이동하면 자동 저장 위치가 첫 평일 메뉴로 바뀝니다.")
        }
        .task { loadLocalArchive() }
        .task(id: beatID) {
            let current = beatID
            refreshAudio(playEffect: true)
            if let beat, let next = beat.next, beat.delay != nil || beat.text?.isEmpty != false {
                let time = UInt64((beat.delay ?? 0) * 1_000_000_000)
                do {
                    try await Task.sleep(nanoseconds: time)
                    if current == beatID { go(to: next) }
                } catch is CancellationError {
                    // A tap, reload, or exit can cancel a timed transition.
                } catch {
                    problem = error.localizedDescription
                }
            }
        }
        .onChange(of: muted) { _ in refreshAudio(playEffect: false) }
    }

    private var titleView: some View {
        ZStack {
            if let library, let artwork = library.image(library.package.program.title) {
                Image(uiImage: artwork)
                    .resizable()
                    .scaledToFit()
                    .accessibilityHidden(true)
            } else {
                LinearGradient(colors: [Color(red: 0.13, green: 0.22, blue: 0.37), .black],
                               startPoint: .topLeading, endPoint: .bottomTrailing)
            }
            VStack(spacing: 14) {
                if library == nil {
                    Spacer()
                    Text("스노우레인")
                        .font(.system(size: 46, weight: .regular, design: .serif))
                    Text("게임 데이터 ZIP을 파일 앱에서 가져오세요.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if importing {
                    ProgressView("게임 데이터 가져오는 중")
                } else {
                    if let library {
                        Button("새 게임") { start(at: library.package.program.start) }
                            .buttonStyle(.borderedProminent)
                        if let resumeSave {
                            Button("이어하기") {
                                growth = resumeSave.growth ?? GrowthStats()
                                go(to: resumeSave.beatID, resuming: true)
                            }
                                .buttonStyle(.bordered)
                        }
                        if library.package.program.firstActivity != nil {
                            Button("첫 평일 메뉴 테스트") { confirmingActivityJump = true }
                                .buttonStyle(.bordered)
                        }
                    }
                    Button(library == nil ? "게임 데이터 가져오기" : "게임 데이터 변경") { pickingArchive = true }
                        .buttonStyle(.bordered)
                }
            }
            .padding(24)
        }
        .overlay(alignment: .topTrailing) {
            if library != nil { soundButton.padding(12) }
        }
    }

    private func playView(library: GameLibrary, beat: StoryProgram.Beat, size: CGSize) -> some View {
        VStack(spacing: 12) {
            HStack {
                Button { beatID = nil } label: { Label("타이틀", systemImage: "chevron.left") }
                Spacer()
                if let date = beat.date {
                    Text(date).font(.subheadline).foregroundStyle(.secondary)
                }
                soundButton
            }
            .padding(.horizontal, 4)

            GeometryReader { stage in
                let width = CGFloat(library.package.program.canvasWidth ?? 360)
                let height = CGFloat(beat.sceneHeight ?? library.package.program.canvasHeight ?? 530)
                let scale = min(stage.size.width / width, stage.size.height / height)
                ZStack {
                    Color.black
                    if let background = library.image(beat.background) {
                        Image(uiImage: background).resizable().scaledToFit()
                            .frame(maxHeight: .infinity, alignment: .top)
                    }
                    ForEach(Array((beat.layers ?? []).enumerated()), id: \.offset) { _, layer in
                        if let image = library.image(layer: layer) {
                            let layerWidth = layer.width.map { CGFloat($0) } ?? image.size.width
                            let layerHeight = layer.height.map { CGFloat($0) } ?? image.size.height
                            Image(uiImage: image)
                                .resizable()
                                .frame(width: layerWidth * scale, height: layerHeight * scale)
                                .scaleEffect(x: layer.mirrored == true ? -1 : 1, y: 1)
                                .opacity(layer.opacity ?? 1)
                                .position(x: ((layer.x.map { CGFloat($0) } ?? (width - layerWidth) / 2) + layerWidth / 2) * scale,
                                          y: ((layer.y.map { CGFloat($0) } ?? height - layerHeight) + layerHeight / 2) * scale)
                        }
                    }
                }
                .frame(width: width * scale, height: height * scale)
                .clipped()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .accessibilityHidden(true)
            }
            if beat.growthStat != nil || beatID == library.package.program.firstActivity {
                HStack {
                    ForEach(Array(zip(GrowthStats.names, growth.values)), id: \.0) { name, value in
                        Text("\(name) \(value)").frame(maxWidth: .infinity)
                    }
                }
                .font(.footnote.monospacedDigit())
            }
            if let line = beat.text, !line.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 7) {
                        if let speaker = beat.speaker {
                            Text(speaker).font(.subheadline.weight(.semibold)).foregroundStyle(Color.cyan)
                        }
                        Text(line)
                            .font(.body)
                            .lineSpacing(5)
                            .textSelection(.enabled)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                }
                .id(beatID)
                .frame(height: min(164, size.height * 0.26))
                .background(.white.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
            }
            if let choices = beat.choices, !choices.isEmpty {
                ScrollView {
                    VStack(spacing: 7) {
                        ForEach(choices) { choice in
                            Button { go(to: choice.target) } label: {
                                Text(choice.text).frame(maxWidth: .infinity, minHeight: 36)
                            }
                        }
                    }
                }
                .frame(height: min(CGFloat(choices.count * 54), size.height * 0.27))
                .buttonStyle(.borderedProminent)
            } else if let next = beat.next, beat.delay == nil, beat.text?.isEmpty == false {
                Button { go(to: next) } label: {
                    Label("다음", systemImage: "chevron.right")
                        .frame(maxWidth: .infinity, minHeight: 34)
                }
                .buttonStyle(.borderedProminent)
            } else if let end = beat.end {
                Text(end).font(.footnote)
                Button("타이틀로") { beatID = nil }.buttonStyle(.bordered)
            }
        }
        .padding(12)
    }

    private var soundButton: some View {
        Button { muted.toggle() } label: {
            Image(systemName: muted ? "speaker.slash" : "speaker.wave.2")
                .frame(minWidth: 44, minHeight: 44)
        }
        .accessibilityLabel(muted ? "소리 켜기" : "소리 끄기")
    }

    private func start(at id: String) {
        growth = GrowthStats()
        go(to: id)
    }

    private func go(to id: String, resuming: Bool = false) {
        guard let library, let target = library.package.program.beats[id], beatID != id else { return }
        if !resuming, let activity = target.growthStat {
            growth.perform(activity: activity, roll: Int.random(in: 0...1000))
        }
        audio.skipEffect = resuming
        beatID = id
        if let data = try? JSONEncoder().encode(StorySave(programID: library.package.id, beatID: id, growth: growth)) {
            saved = data
        }
    }

    private func refreshAudio(playEffect: Bool) {
        let requestedMusic = beatID == nil ? library?.package.program.titleMusic : beat?.music
        audio.update(library: library, music: requestedMusic, effect: playEffect ? beat?.effect : nil, muted: muted)
    }

    private func loadLocalArchive() {
        guard library == nil else { return }
        do {
            let url = try LocalArchive.location()
            if FileManager.default.fileExists(atPath: url.path) {
                library = GameLibrary(package: try StoryPackage(url: url))
                refreshAudio(playEffect: false)
            }
        } catch {
            problem = error.localizedDescription
        }
    }

    private func importArchive(_ url: URL) {
        importing = true
        Task {
            defer { importing = false }
            do {
                let package = try await Task.detached(priority: .userInitiated) {
                    try LocalArchive.install(from: url)
                }.value
                audio.reset()
                library = GameLibrary(package: package)
                beatID = nil
                refreshAudio(playEffect: false)
            } catch {
                problem = error.localizedDescription
            }
        }
    }
}

private final class GameLibrary {
    let package: StoryPackage
    private let images = NSCache<NSString, UIImage>()

    init(package: StoryPackage) {
        self.package = package
        images.countLimit = 32
    }

    func image(_ path: String?) -> UIImage? {
        guard let path else { return nil }
        if let cached = images.object(forKey: path as NSString) { return cached }
        guard let data = try? package.archive.data(path), let image = UIImage(data: data) else { return nil }
        images.setObject(image, forKey: path as NSString)
        return image
    }

    func image(layer: StoryProgram.Layer) -> UIImage? {
        guard let source = image(layer.image) else { return nil }
        guard let x = layer.sourceX, let y = layer.sourceY,
              let width = layer.sourceWidth, let height = layer.sourceHeight else { return source }
        let key = "\(layer.image):\(x),\(y),\(width),\(height)" as NSString
        if let cached = images.object(forKey: key) { return cached }
        let rect = CGRect(x: x, y: y, width: width, height: height)
        guard let cgImage = source.cgImage, rect.width > 0, rect.height > 0,
              CGRect(x: 0, y: 0, width: cgImage.width, height: cgImage.height).contains(rect),
              let cropped = cgImage.cropping(to: rect) else { return nil }
        let image = UIImage(cgImage: cropped)
        images.setObject(image, forKey: key)
        return image
    }
}

private enum LocalArchive {
    static func location() throws -> URL {
        let manager = FileManager.default
        var directory = try manager.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                        appropriateFor: nil, create: true)
            .appendingPathComponent("SnowRain", isDirectory: true)
        try manager.createDirectory(at: directory, withIntermediateDirectories: true)
        var properties = URLResourceValues()
        properties.isExcludedFromBackup = true
        try? directory.setResourceValues(properties)
        return directory.appendingPathComponent("game-data.zip", isDirectory: false)
    }

    static func install(from source: URL) throws -> StoryPackage {
        let access = source.startAccessingSecurityScopedResource()
        defer { if access { source.stopAccessingSecurityScopedResource() } }
        let destination = try location()
        let staging = destination.deletingLastPathComponent().appendingPathComponent(UUID().uuidString + ".zip")
        let manager = FileManager.default
        defer { try? manager.removeItem(at: staging) }
        guard let length = try source.resourceValues(forKeys: [.fileSizeKey]).fileSize,
              (22...512_000_000).contains(length) else { throw StoryError.invalidArchive }
        try manager.copyItem(at: source, to: staging)
        let package = try StoryPackage(url: staging)
        if manager.fileExists(atPath: destination.path) {
            _ = try manager.replaceItemAt(destination, withItemAt: staging)
        } else {
            try manager.moveItem(at: staging, to: destination)
        }
        return package
    }
}

private final class SceneAudio: ObservableObject {
    private var music: AVAudioPlayer?
    private var effect: AVAudioPlayer?
    private var musicPath: String?
    var skipEffect = false

    func update(library: GameLibrary?, music path: String?, effect effectPath: String?, muted: Bool) {
        if muted {
            music?.pause()
            effect?.stop()
            return
        }
        if path != musicPath {
            music?.stop()
            music = player(library: library, path: path)
            music?.numberOfLoops = -1
            musicPath = path
        }
        if music?.isPlaying == false { music?.play() }
        defer { skipEffect = false }
        if !skipEffect, effectPath != nil {
            effect?.stop()
            effect = player(library: library, path: effectPath)
            effect?.play()
        }
    }

    func reset() {
        music?.stop()
        effect?.stop()
        music = nil
        effect = nil
        musicPath = nil
    }

    private func player(library: GameLibrary?, path: String?) -> AVAudioPlayer? {
        guard let library, let path, let data = try? library.package.archive.data(path) else { return nil }
        return try? AVAudioPlayer(data: data)
    }
}
