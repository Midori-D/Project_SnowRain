import Foundation

private enum SmokeFailure: Error {
    case checkFailed(String)
}

private func check(_ condition: @autoclosure () -> Bool, _ message: String) throws {
    if !condition() { throw SmokeFailure.checkFailed(message) }
}

@main
struct StoryPackageSmoke {
    static func main() throws {
        try check(CommandLine.arguments.count == 2, "Pass the fixture directory.")
        let fixtures = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        let package = try StoryPackage(url: fixtures.appendingPathComponent("valid.zip"))
        let story = package.program
        try check(story.start == "opening", "Unexpected new-game entry point.")
        let opening = story.beats[story.start]
        try check(opening?.text == "Pick a path.", "Unexpected opening dialogue.")
        let choices = opening?.next.flatMap { story.beats[$0]?.choices }
        try check(choices?.map(\.text) == ["Left", "Right"], "Choices were lost or reordered.")
        let outcomes = choices?.compactMap { story.beats[$0.target]?.text }
        try check(
            outcomes == ["You visit the garden.", "You cross the bridge."],
            "Choice targets did not preserve the resulting scenes."
        )

        var stats = GrowthStats()
        stats.perform(activity: 0, roll: 199)
        try check(stats.values == [52, 49, 48, 50], "Low study result changed.")
        stats.perform(activity: 1, roll: 200)
        try check(stats.values == [52, 53, 49, 50], "Normal exercise result changed.")
        stats.perform(activity: 3, roll: 700)
        try check(stats.values == [54, 53, 50, 56], "Great sensibility result changed.")
        let saved = StorySave(programID: package.id, beatID: "bridge", growth: stats)
        let restored = try JSONDecoder().decode(StorySave.self, from: JSONEncoder().encode(saved))
        try check(restored.programID == package.id, "The restored save uses the wrong scenario.")
        try check(restored.growth == stats, "Save did not restore growth stats.")
        try check(
            story.beats[restored.beatID]?.text == "You cross the bridge.",
            "Save did not restore the selected branch."
        )

        do {
            _ = try StoryPackage(url: fixtures.appendingPathComponent("corrupt.zip"))
            throw SmokeFailure.checkFailed("ZIP with a changed payload passed integrity checks.")
        } catch StoryError.invalidArchive {
            print("Story package, choice targets, save round trip, and ZIP integrity passed.")
        }
    }
}
