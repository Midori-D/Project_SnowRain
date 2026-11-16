import Foundation
#if canImport(CryptoKit)
import CryptoKit
#endif

/// Reads the uncompressed ZIP format created by the Windows preparation tool.
/// Entries are accessed by name and never extracted to arbitrary file paths.
struct StoryArchive {
    private struct Entry {
        let range: Range<Int>
        let crc: UInt32
    }

    private let bytes: Data
    private let entries: [String: Entry]

    init(url: URL) throws {
        let length = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
        guard (22...512_000_000).contains(length) else { throw StoryError.invalidArchive }
        try self.init(bytes: Data(contentsOf: url, options: .mappedIfSafe))
    }

    init(bytes: Data) throws {
        var entries: [String: Entry] = [:]
        var offset = 0
        while bytes.count - offset >= 30, Self.u32(bytes, at: offset) == 0x04034b50 {
            let flags = Self.u16(bytes, at: offset + 6)
            let method = Self.u16(bytes, at: offset + 8)
            let crc = Self.u32(bytes, at: offset + 14)
            let storedLength = Int(Self.u32(bytes, at: offset + 18))
            let plainLength = Int(Self.u32(bytes, at: offset + 22))
            let nameLength = Self.u16(bytes, at: offset + 26)
            let extraLength = Self.u16(bytes, at: offset + 28)
            let nameStart = offset + 30
            let nameEnd = nameStart + nameLength
            let dataStart = nameEnd + extraLength
            guard flags & ~0x0800 == 0, method == 0, storedLength == plainLength,
                  dataStart <= bytes.count, storedLength <= bytes.count - dataStart,
                  let name = String(data: bytes[nameStart..<nameEnd], encoding: .utf8),
                  !name.contains("\\"), !name.contains("\0"),
                  name.split(separator: "/", omittingEmptySubsequences: false)
                    .allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }),
                  !name.isEmpty, entries[name] == nil else {
                throw StoryError.invalidArchive
            }
            let dataEnd = dataStart + storedLength
            entries[name] = Entry(range: dataStart..<dataEnd, crc: crc)
            offset = dataEnd
        }
        // The generator emits a non-ZIP64 central directory and no ZIP comment.
        guard !entries.isEmpty, bytes.count - offset >= 46 + 22,
              Self.u32(bytes, at: offset) == 0x02014b50,
              Self.u32(bytes, at: bytes.count - 22) == 0x06054b50,
              Self.u16(bytes, at: bytes.count - 12) == entries.count,
              Int(Self.u32(bytes, at: bytes.count - 6)) == offset else {
            throw StoryError.invalidArchive
        }
        self.bytes = bytes
        self.entries = entries
    }

    func contains(_ name: String) -> Bool { entries[name] != nil }

    func data(_ name: String) throws -> Data {
        guard let entry = entries[name] else { throw StoryError.missingAsset(name) }
        let payload = bytes[entry.range]
        let crc = payload.reduce(UInt32.max) { state, byte in
            (state >> 8) ^ Self.crcTable[Int((state ^ UInt32(byte)) & 0xff)]
        } ^ UInt32.max
        guard crc == entry.crc else { throw StoryError.invalidArchive }
        return Data(payload)
    }

    private static func u16(_ data: Data, at i: Int) -> Int {
        Int(data[i]) | Int(data[i + 1]) << 8
    }

    private static func u32(_ data: Data, at i: Int) -> UInt32 {
        UInt32(u16(data, at: i)) | UInt32(u16(data, at: i + 2)) << 16
    }

    private static let crcTable: [UInt32] = (0..<256).map { index in
        (0..<8).reduce(UInt32(index)) { crc, _ in
            crc & 1 == 0 ? crc >> 1 : (crc >> 1) ^ 0xedb88320
        }
    }
}

struct StoryPackage {
    private struct Manifest: Decodable { let formatVersion: Int }

    let archive: StoryArchive
    let program: StoryProgram
    let id: String

    init(url: URL) throws {
        let archive = try StoryArchive(url: url)
        let manifest = try JSONDecoder().decode(Manifest.self, from: archive.data("manifest.json"))
        guard manifest.formatVersion == 1 else { throw StoryError.invalidArchive }
        guard archive.contains("program.json") else { throw StoryError.missingProgram }
        let programData = try archive.data("program.json")
        let program = try JSONDecoder().decode(StoryProgram.self, from: programData)
        try program.validate(hasFile: archive.contains)
        self.archive = archive
        self.program = program
        #if canImport(CryptoKit)
        self.id = SHA256.hash(data: programData).map { String(format: "%02x", $0) }.joined()
        #else
        // The hash is only persisted by the iOS app. This branch supports local test builds.
        self.id = programData.base64EncodedString()
        #endif
    }
}
