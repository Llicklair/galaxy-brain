//! Example wrapper binary showing how to use the gb-hook library.
//!
//! Build and run:
//! ```sh
//! cargo run --bin gb-hook-example
//! ```

fn main() {
    // Install the Galaxy Brain crash hook — do this as early as possible.
    gb_hook::install();

    println!("Application started with Galaxy Brain crash hook active.");
    println!("Any panic from here on will be captured to ~/.galaxy-brain/crashes.jsonl");

    // Simulate application work.
    do_work();
}

fn do_work() {
    // Uncomment the line below to test the hook:
    // panic!("something went wrong in do_work");
    println!("Work completed successfully.");
}
